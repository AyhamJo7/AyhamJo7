"""Prepare the hero portrait from a finished sketch image.

Usage: uv run python scripts/prepare_portrait.py <sketch image>

The sketch should be dark ink on a light paper background. The script converts it to
an "ink mask" (ink white, paper black), feathers the edges so the portrait fades into
the card, and writes src/profile_cards/assets/portrait.webp. The card draws that mask
filled with its own ink colour, so the portrait follows light and dark mode.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

ASSETS = Path(__file__).resolve().parent.parent / "src/profile_cards/assets"
OUTPUT = ASSETS / "portrait.webp"
FIGURE_OUTPUT = ASSETS / "figure.webp"
SIZE_OUTPUT = ASSETS / "portrait.json"

# Two pixels per displayed pixel keeps the halftone crisp on high-density screens.
TARGET_HEIGHT = 800
# Crop away a thin frame some exports carry around the sketch.
EDGE_TRIM = 0.006
# Inverted-grey levels: below the floor is paper noise, above the ceiling is solid ink.
PAPER_FLOOR = 30
INK_CEILING = 190
# Cutting the figure out of the paper: ink brighter than the threshold is a wall, gaps
# up to twice the radius are closed, and the flood starts on the outer edges.
FIGURE_INK_THRESHOLD = 64
FIGURE_GAP_RADIUS = 9
FIGURE_SEED_ROWS = (0.03, 0.30, 0.55)
FIGURE_EDGE_BLUR = 2.4
FLOOD_MARKER = 128
# Fractions of the image over which the edges fade out.
FEATHER_BOTTOM = 0.20
FEATHER_SIDES = 0.07
WEBP_QUALITY = 90


def _levels() -> list[int]:
    """Lookup table: paper noise becomes 0, real ink becomes full strength."""
    span = INK_CEILING - PAPER_FLOOR
    return [
        round(255 * min(1.0, max(0.0, (value - PAPER_FLOOR) / span)))
        for value in range(256)
    ]


def fade_profile(size: int, start: float, end: float) -> bytes:
    """Per-pixel opacity along one axis: 0 up to `start`, rising to 255 at `end`.

    `start` and `end` are fractions of `size`; a profile with start > end fades the
    other way (255 up to `end`, falling to 0 at `start`).
    """
    first, last = start * size, end * size
    values = []
    for i in range(size):
        t = (i + 0.5 - first) / (last - first)
        values.append(round(255 * min(1.0, max(0.0, t))))
    return bytes(values)


def edge_fade(width: int, height: int) -> Image.Image:
    """Opacity that is 255 in the middle and fades to 0 at the sides and bottom."""
    columns = [
        round(left * right / 255)
        for left, right in zip(
            fade_profile(width, 0.0, FEATHER_SIDES),
            fade_profile(width, 1.0, 1.0 - FEATHER_SIDES),
            strict=True,
        )
    ]
    rows = fade_profile(height, 1.0, 1.0 - FEATHER_BOTTOM)
    column_image = Image.frombytes("L", (width, 1), bytes(columns))
    row_image = Image.frombytes("L", (1, height), rows)
    nearest = Image.Resampling.NEAREST
    return ImageChops.multiply(
        column_image.resize((width, height), nearest),
        row_image.resize((width, height), nearest),
    )


def raw_ink(sketch: Path) -> Image.Image:
    """The sketch as an unfaded ink mask: ink white, paper black."""
    image = Image.open(sketch).convert("RGBA")
    paper = Image.new("RGBA", image.size, (255, 255, 255, 255))
    gray = Image.alpha_composite(paper, image).convert("L")

    width, height = gray.size
    trim_x, trim_y = round(width * EDGE_TRIM), round(height * EDGE_TRIM)
    gray = gray.crop((trim_x, trim_y, width - trim_x, height - trim_y))
    width, height = gray.size
    gray = gray.resize(
        (round(width * TARGET_HEIGHT / height), TARGET_HEIGHT),
        Image.Resampling.LANCZOS,
    )

    return ImageOps.invert(gray).point(_levels())


def ink_mask(sketch: Path) -> Image.Image:
    """The ink, faded at the sides and bottom so it melts into the card."""
    ink = raw_ink(sketch)
    return ImageChops.multiply(ink, edge_fade(*ink.size))


def figure_mask(ink: Image.Image) -> Image.Image:
    """The person's outline: 255 inside head, hair and shoulders, 0 on the paper.

    The ink acts as a wall. Small gaps in dotted outlines are closed first, then the
    background is flooded from the outer edges; whatever the flood cannot reach is the
    figure. The edges are not seeded at the bottom, where the open collar would let the
    flood run up into the face. Finally the closing is undone so the outline hugs the
    drawing.
    """
    size = 2 * FIGURE_GAP_RADIUS + 1
    solid = ink.point(lambda v: 255 if v > FIGURE_INK_THRESHOLD else 0)
    flooded = solid.filter(ImageFilter.MaxFilter(size))
    width, height = flooded.size
    seeds = [(1, 1), (width - 2, 1)]
    for fraction in FIGURE_SEED_ROWS:
        row = round(height * fraction)
        seeds += [(1, row), (width - 2, row)]
    for seed in seeds:
        if flooded.getpixel(seed) == 0:
            ImageDraw.floodfill(flooded, seed, FLOOD_MARKER)
    figure = flooded.point(lambda v: 0 if v == FLOOD_MARKER else 255)
    return figure.filter(ImageFilter.MinFilter(size)).filter(
        ImageFilter.GaussianBlur(FIGURE_EDGE_BLUR)
    )


def figure_cutout(sketch: Path) -> Image.Image:
    """The figure outline, faded like the ink."""
    ink = raw_ink(sketch)
    return ImageChops.multiply(figure_mask(ink), edge_fade(*ink.size))


def _save(image: Image.Image, path: Path) -> None:
    image.save(path, "WEBP", quality=WEBP_QUALITY, method=6)
    sys.stdout.write(
        f"{path.name}: {image.width}x{image.height}, {path.stat().st_size} bytes\n"
    )


def main(sketch: Path) -> None:
    ink = ink_mask(sketch)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    _save(ink, OUTPUT)
    _save(figure_cutout(sketch), FIGURE_OUTPUT)
    SIZE_OUTPUT.write_text(
        json.dumps({"width": ink.width, "height": ink.height}) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]))

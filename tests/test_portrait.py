from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

import prepare_portrait
from profile_cards.portrait import MEDIA_TYPE, load_portrait

PAPER = (244, 243, 234, 255)
INK = (53, 59, 64, 255)
SKETCH_SIZE = (300, 400)


def grey(image: Image.Image, position: tuple[int, int]) -> int:
    """One pixel of a single-channel image, typed for the checker."""
    value = image.getpixel(position)
    assert isinstance(value, int)
    return value


def synthetic_sketch(path: Path) -> Path:
    """Dark ink shapes on slightly noisy paper."""
    image = Image.new("RGBA", SKETCH_SIZE, PAPER)
    draw = ImageDraw.Draw(image)
    draw.ellipse((90, 120, 210, 240), fill=INK)
    draw.point([(x, 5) for x in range(0, 300, 3)], fill=(236, 235, 226, 255))
    image.save(path)
    return path


def ring_sketch(path: Path, *, gap: bool) -> Path:
    """A closed ring of ink around paper, optionally with a small gap in the wall."""
    image = Image.new("RGBA", SKETCH_SIZE, PAPER)
    draw = ImageDraw.Draw(image)
    draw.ellipse((60, 80, 240, 300), outline=INK, width=10)
    if gap:
        draw.rectangle((235, 180, 250, 190), fill=PAPER)
    image.save(path)
    return path


def test_figure_mask_fills_the_inside_of_the_outline_and_clears_the_outside(
    tmp_path: Path,
) -> None:
    ink = prepare_portrait.raw_ink(ring_sketch(tmp_path / "ring.png", gap=False))
    figure = prepare_portrait.figure_mask(ink)
    inside = (figure.width // 2, int(figure.height * 0.47))
    outside = (figure.width // 12, figure.height // 2)
    assert grey(figure, inside) == 255
    assert grey(figure, outside) == 0


def test_figure_mask_does_not_leak_through_a_small_gap_in_the_outline(
    tmp_path: Path,
) -> None:
    ink = prepare_portrait.raw_ink(ring_sketch(tmp_path / "ring.png", gap=True))
    figure = prepare_portrait.figure_mask(ink)
    assert grey(figure, (figure.width // 2, int(figure.height * 0.47))) == 255


def test_the_bundled_portrait_loads_as_an_embeddable_webp() -> None:
    portrait = load_portrait()
    assert portrait is not None, "run scripts/prepare_portrait.py"
    assert portrait.data_uri.startswith(f"data:{MEDIA_TYPE};base64,")
    assert portrait.figure_uri.startswith(f"data:{MEDIA_TYPE};base64,")
    assert portrait.figure_uri != portrait.data_uri
    assert portrait.width > 0
    assert portrait.height > 0
    assert 0.5 < portrait.aspect < 1.5


def test_levels_turn_paper_noise_into_nothing_and_ink_into_full_strength() -> None:
    levels = prepare_portrait._levels()
    assert len(levels) == 256
    assert levels[0] == 0
    assert levels[prepare_portrait.PAPER_FLOOR] == 0
    assert levels[255 - 244] == 0, "paper must vanish"
    assert levels[255 - 53] == 255, "ink must be solid"
    assert levels == sorted(levels)


def test_fade_profile_rises_and_falls_as_asked() -> None:
    rising = prepare_portrait.fade_profile(100, 0.0, 0.1)
    falling = prepare_portrait.fade_profile(100, 1.0, 0.9)
    assert rising[0] < 60
    assert rising[-1] == 255
    assert falling[0] == 255
    assert falling[-1] < 60
    assert list(rising) == sorted(rising)
    assert list(falling) == sorted(falling, reverse=True)


def test_ink_mask_keeps_ink_clears_paper_and_fades_the_bottom(
    tmp_path: Path,
) -> None:
    mask = prepare_portrait.ink_mask(synthetic_sketch(tmp_path / "sketch.png"))
    assert mask.height == prepare_portrait.TARGET_HEIGHT
    centre = (mask.width // 2, int(mask.height * 0.45))
    paper = (mask.width // 2, int(mask.height * 0.05))
    assert grey(mask, centre) == 255
    assert grey(mask, paper) == 0
    fade = prepare_portrait.edge_fade(mask.width, mask.height)
    assert grey(fade, (mask.width // 2, mask.height - 1)) < 10
    assert grey(fade, (mask.width // 2, mask.height // 2)) == 255
    assert grey(fade, (0, mask.height // 2)) < 10

"""Subset the source fonts to the characters the cards can contain.

Usage: uv run python scripts/subset_fonts.py <directory holding the source woff2 files>

The sources are the Latin builds of @fontsource/instrument-serif,
@fontsource/jetbrains-mono and @fontsource/inter (all SIL OFL 1.1). The subsets are
written to src/profile_cards/fonts/ and embedded into every card, so the cards look the
same on every machine and need no network access.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fontTools import subset

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "src" / "profile_cards" / "fonts"

# source file -> subset file
FONTS = {
    "instrument-serif-latin-400-normal.woff2": "serif.woff2",
    "instrument-serif-latin-400-italic.woff2": "serif-italic.woff2",
    "jetbrains-mono-latin-500-normal.woff2": "mono.woff2",
    "inter-latin-500-normal.woff2": "sans.woff2",
}

# Basic Latin plus the typographic punctuation GitHub descriptions commonly use.
UNICODES = [
    *range(0x20, 0x7F),
    0xA0,  # no-break space
    0xB7,  # middle dot
    0xD7,  # multiplication sign
    0x2013,  # en dash
    0x2014,  # em dash
    0x2018,
    0x2019,  # single quotes
    0x201C,
    0x201D,  # double quotes
    0x2022,  # bullet
    0x2026,  # ellipsis
    0x2605,  # black star
]


def main(source_dir: Path) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = ["kern", "liga", "tnum", "calt"]
    options.notdef_outline = True
    for source_name, target_name in FONTS.items():
        font = subset.load_font(str(source_dir / source_name), options)
        subsetter = subset.Subsetter(options)
        subsetter.populate(unicodes=UNICODES)
        subsetter.subset(font)
        target = OUTPUT_DIR / target_name
        subset.save_font(font, str(target), options)
        print(f"{target_name}: {target.stat().st_size} bytes")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]))

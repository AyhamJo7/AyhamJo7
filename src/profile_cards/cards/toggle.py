"""Toggle card: the small pill that opens the card for the 12 months before.

It is the content of an HTML `<summary>` in the README, so GitHub makes it a real
button even though an SVG shown as an image cannot be clicked itself.
"""

from __future__ import annotations

from profile_cards.config import Config
from profile_cards.model import Snapshot
from profile_cards.theme import document, esc, mono_width

LABEL = "The 12 months before"
WIDTH = 252
HEIGHT = 52
PILL_HEIGHT = 36
PILL_PAD_X = 20
FONT_PX = 14
CHEVRON_SIZE = 12
CHEVRON_GAP = 12


def render(config: Config, snapshot: Snapshot) -> str:
    text_width = mono_width(LABEL, FONT_PX)
    pill_width = PILL_PAD_X * 2 + text_width + CHEVRON_GAP + CHEVRON_SIZE
    x = (WIDTH - pill_width) / 2
    y = (HEIGHT - PILL_HEIGHT) / 2
    chevron_x = x + PILL_PAD_X + text_width + CHEVRON_GAP
    chevron_y = y + PILL_HEIGHT / 2 - CHEVRON_SIZE / 4
    body = (
        f'<rect class="solid" x="{x:.1f}" y="{y:.1f}" width="{pill_width:.1f}" '
        f'height="{PILL_HEIGHT}" rx="{PILL_HEIGHT / 2}"/>'
        f'<text class="mono" x="{x + PILL_PAD_X:.1f}" y="{y + 23:.1f}" '
        f'font-size="{FONT_PX}" fill="#fff">{esc(LABEL)}</text>'
        f'<path class="bob" d="M{chevron_x:.1f} {chevron_y:.1f} '
        f"l{CHEVRON_SIZE / 2:g} {CHEVRON_SIZE / 2:g} "
        f'l{CHEVRON_SIZE / 2:g} -{CHEVRON_SIZE / 2:g}" stroke="#fff" '
        'stroke-width="1.8" fill="none" stroke-linecap="round" '
        'stroke-linejoin="round"/>'
    )
    return document(
        WIDTH,
        HEIGHT,
        body,
        title="Show the 12 months before",
        description=(
            f"Opens the contribution card for the 12 months before the latest "
            f"ones, for {config.login}."
        ),
        fonts=("mono",),
    )

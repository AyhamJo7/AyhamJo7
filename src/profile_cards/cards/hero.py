"""Hero card: name with a moving blue light, role, one sentence, a link, a portrait."""

from __future__ import annotations

from profile_cards.config import Config
from profile_cards.model import Snapshot
from profile_cards.portrait import load_portrait
from profile_cards.theme import (
    card_rect,
    document,
    esc,
    fmt_int,
    live_dot,
    mono_width,
    wrap,
)

WIDTH = 880
HEIGHT = 446
TEXT_X = 36
NAME_FONT_PX = 104
NAME_BASELINES = (170, 262)
NAME_LETTER_SPACING = "-.025em"
TAGLINE_TOP = 322
TAGLINE_WIDTH = 390
TAGLINE_FONT_PX = 16
TAGLINE_LINE_HEIGHT = 22
PILL_HEIGHT = 32
PILL_PAD_X = 18
PILL_FONT_PX = 14
ARROW_SIZE = 9
PORTRAIT_RIGHT = 846
PORTRAIT_TOP = 30
PORTRAIT_HEIGHT = 388
PORTRAIT_DELAY_SECONDS = 0.15
PORTRAIT_REVEAL_SECONDS = 1.6
SWEEP_WIDTH = 150
SWEEP_LEAD = 100
SWEEP_SKEW_DEGREES = -18
SWEEP_TOP = 70
SWEEP_HEIGHT = 250
SWEEP_REVEAL_DELAYS = (0.0, 0.12)


def _portrait() -> str:
    """The sketch: the card's ink seen through the portrait mask, right-aligned."""
    portrait = load_portrait()
    if portrait is None:
        return ""
    height = PORTRAIT_HEIGHT
    width = height * portrait.aspect
    x = PORTRAIT_RIGHT - width
    box = f'x="{x:.1f}" y="{PORTRAIT_TOP}" width="{width:.1f}" height="{height}"'
    timing = (
        f'style="animation-delay:{PORTRAIT_DELAY_SECONDS}s;'
        f'animation-duration:{PORTRAIT_REVEAL_SECONDS}s"'
    )

    def mask(identifier: str, uri: str) -> str:
        return (
            f'<mask id="{identifier}" maskUnits="userSpaceOnUse" {box}>'
            f'<image href="{uri}" {box} preserveAspectRatio="none"/></mask>'
        )

    return (
        f"<defs>{mask('figure', portrait.figure_uri)}"
        f"{mask('portrait', portrait.data_uri)}</defs>"
        f'<rect class="panel rise" mask="url(#figure)" {box} {timing}/>'
        f'<rect class="sketch rise" mask="url(#portrait)" {box} {timing}/>'
    )


def _sweep_defs() -> str:
    """A soft slanted band of light, used as a mask over copies of the name."""
    return (
        '<defs><linearGradient id="band">'
        '<stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        '<stop offset=".5" stop-color="#fff"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity="0"/>'
        "</linearGradient>"
        f'<mask id="sweep" maskUnits="userSpaceOnUse" x="0" y="{SWEEP_TOP}" '
        f'width="{WIDTH}" height="{SWEEP_HEIGHT}">'
        f'<g transform="skewX({SWEEP_SKEW_DEGREES})">'
        f'<rect class="sweep" x="{-(SWEEP_WIDTH + SWEEP_LEAD)}" y="0" '
        f'width="{SWEEP_WIDTH}" height="{SWEEP_TOP + SWEEP_HEIGHT}" '
        f'fill="url(#band)"/></g></mask></defs>'
    )


def _name(config: Config) -> str:
    """First name in ink, last name in blue italic; a light sweeps through both."""
    style = f"letter-spacing:{NAME_LETTER_SPACING}"
    lines = (
        (config.first_name, "serif", "ink", "accent"),
        (config.last_name, "serif it", "accent", "sheen"),
    )
    out = []
    for (text, font, base, glow), baseline, reveal in zip(
        lines, NAME_BASELINES, SWEEP_REVEAL_DELAYS, strict=True
    ):
        common = (
            f'x="{TEXT_X - 2}" y="{baseline}" font-size="{NAME_FONT_PX}" '
            f'style="{style};animation-delay:{reveal}s"'
        )
        out.append(f'<text class="{font} {base} rise" {common}>{esc(text)}</text>')
        out.append(
            f'<text class="{font} {glow} rise" mask="url(#sweep)" {common}>'
            f"{esc(text)}</text>"
        )
    return "".join(out)


def _pill(label: str, y: int) -> str:
    text_w = mono_width(label, PILL_FONT_PX)
    width = PILL_PAD_X * 2 + text_w + 10 + ARROW_SIZE
    arrow_x = TEXT_X + PILL_PAD_X + text_w + 10
    top = y + (PILL_HEIGHT - ARROW_SIZE) / 2
    return (
        f'<rect class="solid" x="{TEXT_X}" y="{y}" width="{width:.1f}" '
        f'height="{PILL_HEIGHT}" rx="{PILL_HEIGHT / 2}"/>'
        f'<text class="mono" x="{TEXT_X + PILL_PAD_X}" y="{y + 21}" '
        f'font-size="{PILL_FONT_PX}" fill="#fff">{esc(label)}</text>'
        f'<path d="M{arrow_x:.1f} {top + ARROW_SIZE:.1f} '
        f"L{arrow_x + ARROW_SIZE:.1f} {top:.1f} "
        f"M{arrow_x + 1:.1f} {top:.1f} H{arrow_x + ARROW_SIZE:.1f} "
        f'V{top + ARROW_SIZE - 1:.1f}" stroke="#fff" stroke-width="1.8" '
        f'fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
    )


def render(config: Config, snapshot: Snapshot) -> str:
    lines = wrap(config.tagline, TAGLINE_WIDTH, TAGLINE_FONT_PX)
    tagline = "".join(
        f'<text class="sans muted" x="{TEXT_X}" '
        f'y="{TAGLINE_TOP + i * TAGLINE_LINE_HEIGHT}" font-size="{TAGLINE_FONT_PX}">'
        f"{esc(line)}</text>"
        for i, line in enumerate(lines)
    )
    pill_y = TAGLINE_TOP + len(lines) * TAGLINE_LINE_HEIGHT + 10
    eyebrow = f"{config.role} · {config.location}"
    body = (
        card_rect(WIDTH, HEIGHT)
        + _sweep_defs()
        + _portrait()
        + live_dot(TEXT_X + 4, 62)
        + f'<text class="cap muted" x="{TEXT_X + 18}" y="66">{esc(eyebrow)}</text>'
        + _name(config)
        + tagline
        + _pill(config.site_label, pill_y)
    )
    return document(
        WIDTH,
        HEIGHT,
        body,
        title=f"{config.name}, {config.role}",
        description=(
            f"{config.name}, {config.role} in {config.location}. {config.tagline} "
            f"{fmt_int(snapshot.total)} contributions in the last year."
        ),
        fonts=("serif", "serif-italic", "mono", "sans"),
    )

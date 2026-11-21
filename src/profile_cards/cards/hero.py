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
NAME_REVEAL_DELAYS = (0.0, 0.12)
# The travelling light: a slanted band that crosses the name, then the portrait.
GLOW_ON_INK = "glowOnInk"
GLOW_ON_BLUE = "glowOnBlue"
GLOW_WIDTH = 190
GLOW_SKEW_DEGREES = -18
# Where the band rests before it starts, and where its left edge ends up. The end is
# past the portrait's right edge, allowing for the slant at the top of the card.
GLOW_REST_X = 420
GLOW_END_X = 1000
GLOW_BEGIN_SECONDS = 1.6
GLOW_SECONDS = 9.0
GLOW_TRAVEL_FRACTION = 0.6
# Constant speed, so the light moves through the letters instead of flashing past.
GLOW_EASING = "0 0 1 1"


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
        f'<rect class="glow rise" mask="url(#portrait)" {box} '
        f'style="fill:url(#{GLOW_ON_INK});animation-delay:{PORTRAIT_DELAY_SECONDS}s;'
        f'animation-duration:{PORTRAIT_REVEAL_SECONDS}s"/>'
    )


def _glow_defs() -> str:
    """Two slanted bands of light that travel across the whole card, left to right.

    Each is a gradient in card coordinates (transparent, colour, transparent) whose
    transform is animated natively, so one band passes over the name and then the
    portrait. The band rests far off the left edge before it starts and between runs.
    """
    start, end = -GLOW_REST_X, GLOW_END_X
    travel = (
        f'<animateTransform attributeName="gradientTransform" type="translate" '
        f'additive="sum" values="0 0;{end - start} 0;{end - start} 0" '
        f'keyTimes="0;{GLOW_TRAVEL_FRACTION};1" calcMode="spline" '
        f'keySplines="{GLOW_EASING};0 0 1 1" dur="{GLOW_SECONDS}s" '
        f'begin="{GLOW_BEGIN_SECONDS}s" repeatCount="indefinite"/>'
    )

    def gradient(identifier: str, color: str) -> str:
        stops = "".join(
            f'<stop offset="{offset}" style="stop-color:var({color});'
            f'stop-opacity:{opacity}"/>'
            for offset, opacity in ((0, 0), (0.5, 1), (1, 0))
        )
        return (
            f'<linearGradient id="{identifier}" gradientUnits="userSpaceOnUse" '
            f'x1="0" y1="0" x2="{GLOW_WIDTH}" y2="0" '
            f'gradientTransform="skewX({GLOW_SKEW_DEGREES}) translate({start} 0)">'
            f"{stops}{travel}</linearGradient>"
        )

    return (
        f"<defs>{gradient(GLOW_ON_INK, '--accent')}"
        f"{gradient(GLOW_ON_BLUE, '--sheen')}</defs>"
    )


def _name(config: Config) -> str:
    """First name in ink, last name in blue italic; the light passes through both."""
    style = f"letter-spacing:{NAME_LETTER_SPACING}"
    lines = (
        (config.first_name, "serif", "ink", GLOW_ON_INK),
        (config.last_name, "serif it", "accent", GLOW_ON_BLUE),
    )
    out = []
    for (text, font, base, glow), baseline, reveal in zip(
        lines, NAME_BASELINES, NAME_REVEAL_DELAYS, strict=True
    ):
        timing = f"{style};animation-delay:{reveal}s"
        out.append(
            f'<text class="{font} {base} rise" x="{TEXT_X - 2}" y="{baseline}" '
            f'font-size="{NAME_FONT_PX}" style="{timing}">{esc(text)}</text>'
        )
        out.append(
            f'<text class="{font} glow rise" x="{TEXT_X - 2}" y="{baseline}" '
            f'font-size="{NAME_FONT_PX}" style="{timing};fill:url(#{glow})">'
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
        + _glow_defs()
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

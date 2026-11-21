"""Hero card: name with a moving blue light, role, one sentence, a link, a portrait."""

from __future__ import annotations

from profile_cards.config import Config
from profile_cards.model import Snapshot
from profile_cards.portrait import load_portrait
from profile_cards.theme import (
    DARK,
    LIGHT,
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

# The travelling light. Each surface is filled with a gradient that is its own colour
# with one soft band of a brighter colour; the gradient's transform is animated with a
# plain SVG `animateTransform`, so the band slides across the name and then the
# portrait. This is the same mechanism as a CSS-free "shine" and it cannot be switched
# off by a media query, so it plays for everyone.
SHINE_LENGTH = 700
# The gradient vector tilts up to the right, which slants the band like italics.
SHINE_SLANT = 150
SHINE_BAND_STOPS = (0.0, 0.4, 0.5, 0.6, 1.0)
# Where the gradient rests before the first pass, far enough left to be off the card.
SHINE_REST_X = -700
# One pass as (seconds after the image loads, translation of the gradient) points.
# Motion is linear between points. Read left to right:
#   1.5 s  the light reaches "Ayham" and "Joumran" and slides through them
#          (about 128 px/s); it has left "Ayham" by about 3.8 s
#   3.8 s  a quick hop (about 286 px/s) off the end of "Joumran" (gone by about 4.2 s)
#   4.3 s  the light reaches the photo and has crossed it by 6.5 s (about 169 px/s)
#   7.0 s  the band has left the card, and it rests there until the next pass
#   8.0 s  the next pass starts, so a pass repeats every 6.5 s
# The speeds differ because the requested times for the three surfaces cannot all be met
# at one constant speed. The translations were calibrated against real-time frames.
SHINE_PATH = ((1.5, -400), (3.8, -105), (4.3, 38), (6.5, 410), (7.0, 540), (8.0, 540))
# (class name, gradient name, base colour key, band colour key)
SHINE_SURFACES = (
    ("shine-name", "shineName", "ink", "accent"),
    ("shine-surname", "shineSurname", "accent", "sheen"),
    ("shine-sketch", "shineSketch", "sketch", "accent"),
)


def _shine_gradient(identifier: str, base: str, band: str) -> str:
    colours = (base, base, band, base, base)
    stops = "".join(
        f'<stop offset="{offset}" stop-color="{colour}"/>'
        for offset, colour in zip(SHINE_BAND_STOPS, colours, strict=True)
    )
    begin, end = SHINE_PATH[0][0], SHINE_PATH[-1][0]
    key_times = ";".join(f"{(t - begin) / (end - begin):.4f}" for t, _ in SHINE_PATH)
    values = ";".join(f"{x} 0" for _, x in SHINE_PATH)
    travel = (
        f'<animateTransform attributeName="gradientTransform" type="translate" '
        f'values="{values}" keyTimes="{key_times}" dur="{end - begin:g}s" '
        f'begin="{begin:g}s" repeatCount="indefinite"/>'
    )
    return (
        f'<linearGradient id="{identifier}" gradientUnits="userSpaceOnUse" '
        f'x1="0" y1="0" x2="{SHINE_LENGTH}" y2="{-SHINE_SLANT}" '
        f'gradientTransform="translate({SHINE_REST_X} 0)">{stops}{travel}'
        "</linearGradient>"
    )


def _shine_defs() -> str:
    """One gradient per surface and colour scheme, with literal colours."""
    gradients = []
    for _, name, base, band in SHINE_SURFACES:
        for scheme, palette in (("Light", LIGHT), ("Dark", DARK)):
            gradients.append(
                _shine_gradient(f"{name}{scheme}", palette[base], palette[band])
            )
    return f"<defs>{''.join(gradients)}</defs>"


def _shine_css() -> str:
    """Fill each surface with its light gradient, or its dark one in dark mode."""

    def rules(scheme: str) -> str:
        return "".join(
            f".{cls}{{fill:url(#{name}{scheme})}}" for cls, name, _, _ in SHINE_SURFACES
        )

    return f"{rules('Light')}@media(prefers-color-scheme:dark){{{rules('Dark')}}}"


def _portrait() -> str:
    """The sketch: a paper-coloured figure, and the portrait ink drawn on top of it."""
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
        f'<rect class="shine-sketch rise" mask="url(#portrait)" {box} {timing}/>'
    )


def _name(config: Config) -> str:
    """First name in ink, last name in blue italic; the light slides through both."""
    style = f"letter-spacing:{NAME_LETTER_SPACING}"
    lines = (
        (config.first_name, "serif shine-name"),
        (config.last_name, "serif it shine-surname"),
    )
    return "".join(
        f'<text class="{classes} rise" x="{TEXT_X - 2}" y="{baseline}" '
        f'font-size="{NAME_FONT_PX}" style="{style};animation-delay:{reveal}s">'
        f"{esc(text)}</text>"
        for (text, classes), baseline, reveal in zip(
            lines, NAME_BASELINES, NAME_REVEAL_DELAYS, strict=True
        )
    )


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
        + _shine_defs()
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
        extra_css=_shine_css(),
    )

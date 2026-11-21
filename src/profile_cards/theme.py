"""Shared look of the cards: palette, light and dark CSS, animations, fonts."""

from __future__ import annotations

import base64
import textwrap
from collections.abc import Iterable
from functools import cache
from importlib import resources
from xml.sax.saxutils import escape

from profile_cards.stats import LEVELS

CARD_INSET = 6
CARD_RADIUS = 26
SIDE_SHADE_LEFT = 0.82
SIDE_SHADE_RIGHT = 0.66
SANS_CHAR_WIDTH = 0.56
MONO_CHAR_WIDTH = 0.6

# The five blues of the heatmap, light then dark. Level 4 is the brand blue.
LIGHT_RAMP = ("#c8d3ff", "#94a8ff", "#6280ff", "#2f55ff", "#1a3be0")
DARK_RAMP = ("#222f78", "#2f49b8", "#4a69ff", "#7d95ff", "#b6c3ff")

LIGHT = {
    "bg": "#f3f3f1",
    "ink": "#111111",
    "muted": "#6e6e73",
    "empty": "#e2e2de",
    "line": "#d9d9d4",
    "accent": "#2f55ff",
    "sheen": "#b4c3ff",
    "panel": "#f3f3f1",
    "sketch": "#111111",
    "solid": "#2f55ff",
}
DARK = {
    "bg": "#17181c",
    "ink": "#f3f3f1",
    "muted": "#9a9aa2",
    "empty": "#26272d",
    "line": "#2d2e35",
    "accent": "#7d95ff",
    "sheen": "#eef1ff",
    "panel": "#f3f3f1",
    "sketch": "#2a3038",
    "solid": "#3b5cff",
}

FONT_FILES = {
    "serif": ("PC Serif", "normal", "serif.woff2"),
    "serif-italic": ("PC Serif", "italic", "serif-italic.woff2"),
    "mono": ("PC Mono", "normal", "mono.woff2"),
    "sans": ("PC Sans", "normal", "sans.woff2"),
}


def esc(text: str) -> str:
    """Escape text for use in SVG content or a double-quoted attribute."""
    return escape(text, {'"': "&quot;"})


def fmt_int(value: int) -> str:
    return f"{value:,}"


def compact(value: int) -> str:
    """1,234 -> 1.2K, 766,000 -> 766K, 1,200,000 -> 1.2M."""
    for size, suffix in ((1_000_000, "M"), (1_000, "K")):
        if value >= size:
            scaled = value / size
            text = f"{scaled:.0f}" if scaled >= 100 else f"{scaled:.1f}"
            return text.removesuffix(".0") + suffix
    return str(value)


def wrap(text: str, width_px: float, font_px: float) -> list[str]:
    """Wrap sans-serif text to an approximate pixel width."""
    max_chars = max(8, int(width_px / (font_px * SANS_CHAR_WIDTH)))
    return textwrap.wrap(text, max_chars) or [""]


def shade(color: str, factor: float) -> str:
    channels = [int(color[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(c * factor):02x}" for c in channels)


def _ramp_vars(ramp: tuple[str, ...]) -> str:
    rows = []
    for level, color in enumerate(ramp, start=1):
        rows.append(f"--l{level}:{color};")
        rows.append(f"--l{level}s:{shade(color, SIDE_SHADE_LEFT)};")
        rows.append(f"--l{level}r:{shade(color, SIDE_SHADE_RIGHT)};")
    return "".join(rows)


def _vars(palette: dict[str, str], ramp: tuple[str, ...]) -> str:
    base = "".join(f"--{key}:{value};" for key, value in palette.items())
    return base + _ramp_vars(ramp)


def _level_classes() -> str:
    return "".join(
        f".t{n}{{fill:var(--l{n})}}.s{n}{{fill:var(--l{n}s)}}.r{n}{{fill:var(--l{n}r)}}"
        for n in range(1, LEVELS + 1)
    )


@cache
def _font_data(name: str) -> str:
    data = resources.files("profile_cards").joinpath("fonts", name).read_bytes()
    return base64.b64encode(data).decode("ascii")


def _font_faces(fonts: Iterable[str]) -> str:
    faces = []
    for key in fonts:
        family, style, file = FONT_FILES[key]
        faces.append(
            f"@font-face{{font-family:'{family}';font-style:{style};"
            f"src:url(data:font/woff2;base64,{_font_data(file)}) format('woff2')}}"
        )
    return "".join(faces)


STYLE = (
    f":root{{{_vars(LIGHT, LIGHT_RAMP)}}}"
    f"@media(prefers-color-scheme:dark){{:root{{{_vars(DARK, DARK_RAMP)}}}}}"
    ".card{fill:var(--bg)}.ink{fill:var(--ink)}.muted{fill:var(--muted)}"
    ".accent{fill:var(--accent)}.empty{fill:var(--empty)}"
    ".solid{fill:var(--solid)}.line{stroke:var(--line);fill:none}"
    ".panel{fill:var(--panel)}.sketch{fill:var(--sketch)}"
    ".paper{fill:var(--bg)}"
    ".serif{font-family:'PC Serif',Georgia,'Times New Roman',serif}"
    ".it{font-style:italic}"
    ".mono{font-family:'PC Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}"
    ".sans{font-family:'PC Sans',-apple-system,'Segoe UI',Helvetica,Arial,sans-serif}"
    ".cap{font-family:'PC Mono',ui-monospace,Menlo,Consolas,monospace;"
    "font-size:12px;letter-spacing:.14em;text-transform:uppercase}"
    f"{_level_classes()}"
    "@keyframes rise{from{opacity:0;transform:translateY(10px)}}"
    "@keyframes pop{from{opacity:0;transform:scale(.3)}}"
    "@keyframes grow{from{transform:scaleY(0)}}"
    "@keyframes pulse{0%,100%{opacity:1}50%{opacity:.25}}"
    "@keyframes ping{0%{opacity:.9;transform:scale(1)}"
    "100%{opacity:0;transform:scale(2.6)}}"
    "@keyframes draw{from{stroke-dashoffset:var(--len)}}"
    ".rise{animation:rise .9s cubic-bezier(.2,.7,.2,1) both}"
    ".pop{transform-box:fill-box;transform-origin:center;"
    "animation:pop .55s cubic-bezier(.2,.9,.3,1.3) both}"
    ".grow{transform-box:fill-box;transform-origin:50% 100%;"
    "animation:grow .9s cubic-bezier(.2,.8,.2,1) both}"
    ".live{animation:pulse 2.4s ease-in-out infinite}"
    ".ping{transform-box:fill-box;transform-origin:center;"
    "animation:ping 2.4s ease-out infinite}"
    ".draw{stroke-dasharray:var(--len);animation:draw 1.6s ease-out both}"
)


def delay(seconds: float) -> str:
    return f'style="animation-delay:{seconds:.2f}s"'


def document(  # noqa: PLR0913 - one wrapper shared by every card
    width: int,
    height: int,
    body: str,
    *,
    title: str,
    description: str,
    fonts: Iterable[str],
    extra_css: str = "",
) -> str:
    """Wrap card content into a standalone SVG document."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-labelledby="t d">'
        f'<title id="t">{esc(title)}</title><desc id="d">{esc(description)}</desc>'
        f"<style>{_font_faces(fonts)}{STYLE}{extra_css}</style>{body}</svg>\n"
    )


def card_rect(width: int, height: int) -> str:
    return (
        f'<rect class="card" x="{CARD_INSET}" y="{CARD_INSET}" '
        f'width="{width - 2 * CARD_INSET}" height="{height - 2 * CARD_INSET}" '
        f'rx="{CARD_RADIUS}"/>'
    )


def live_dot(x: float, y: float, cls: str = "accent") -> str:
    """A small dot with a ping ring, used as a 'live' marker."""
    return (
        f'<circle class="{cls} ping" cx="{x}" cy="{y}" r="4"/>'
        f'<circle class="{cls}" cx="{x}" cy="{y}" r="4"/>'
    )


def mono_width(text: str, font_px: float) -> float:
    return len(text) * font_px * MONO_CHAR_WIDTH

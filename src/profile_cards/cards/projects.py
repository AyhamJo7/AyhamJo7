"""Project cards: a title banner and one card per featured repository."""

from __future__ import annotations

import math

from profile_cards.config import Config
from profile_cards.model import Project, Snapshot
from profile_cards.theme import (
    MONO_CHAR_WIDTH,
    card_rect,
    delay,
    document,
    esc,
    fmt_int,
    wrap,
)

TITLE_WIDTH = 880
TITLE_HEIGHT = 92
CARD_WIDTH = 296
CARD_HEIGHT = 312
MARGIN_X = 30
CONTENT_WIDTH = CARD_WIDTH - 2 * MARGIN_X
NAME_MAX_FONT_PX = 40
NAME_MIN_FONT_PX = 20
SERIF_CHAR_WIDTH = 0.44
BLURB_FONT_PX = 13.5
BLURB_LINE_HEIGHT = 20
BLURB_MAX_LINES = 4
BLURB_TOP = 150
SPARK_BASELINE = 268
SPARK_MAX_HEIGHT = 40
SPARK_MIN_HEIGHT = 3
SPARK_BAR_WIDTH = 14
CAPTION_BASELINE = 296
CAPTION_FONT_PX = 11
STAR_RADIUS = 6


def render_title(config: Config, snapshot: Snapshot) -> str:
    body = (
        card_rect(TITLE_WIDTH, TITLE_HEIGHT)
        + '<text class="serif ink" x="36" y="68" font-size="44" '
        'style="letter-spacing:-.02em">What I\'m <tspan class="it accent">coding'
        "</tspan></text>"
        + f'<text class="cap muted" x="{TITLE_WIDTH - 36}" y="62" text-anchor="end">'
        "Live from GitHub · last 12 weeks</text>"
    )
    return document(
        TITLE_WIDTH,
        TITLE_HEIGHT,
        body,
        title="What I'm coding",
        description=f"The projects {config.login} is building right now.",
        fonts=("serif", "serif-italic", "mono"),
    )


def _star(cx: float, cy: float, radius: float) -> str:
    points = []
    for i in range(10):
        r = radius if i % 2 == 0 else radius * 0.42
        angle = -math.pi / 2 + i * math.pi / 5
        points.append(f"{cx + r * math.cos(angle):.1f},{cy + r * math.sin(angle):.1f}")
    return f'<polygon class="muted" points="{" ".join(points)}"/>'


def _blurb(text: str) -> str:
    lines = wrap(text, CONTENT_WIDTH, BLURB_FONT_PX)
    if len(lines) > BLURB_MAX_LINES:
        lines = lines[:BLURB_MAX_LINES]
        lines[-1] = lines[-1].rstrip(" ,.;:") + "…"
    return "".join(
        f'<text class="sans muted" x="{MARGIN_X}" '
        f'y="{BLURB_TOP + i * BLURB_LINE_HEIGHT}" font-size="{BLURB_FONT_PX}">'
        f"{esc(line)}</text>"
        for i, line in enumerate(lines)
    )


def _sparkline(weekly: tuple[int, ...]) -> str:
    peak = max(weekly) or 1
    pitch = (CONTENT_WIDTH - SPARK_BAR_WIDTH) / max(1, len(weekly) - 1)
    bars = []
    for i, commits in enumerate(weekly):
        height = max(SPARK_MIN_HEIGHT, commits / peak * SPARK_MAX_HEIGHT)
        cls = "t4" if commits else "empty"
        bars.append(
            f'<rect class="grow {cls}" x="{MARGIN_X + i * pitch:.1f}" '
            f'y="{SPARK_BASELINE - height:.1f}" width="{SPARK_BAR_WIDTH}" '
            f'height="{height:.1f}" rx="4" {delay(0.2 + i * 0.05)}/>'
        )
    return "".join(bars)


def render_project(config: Config, project: Project, index: int) -> str:
    name_px = max(
        NAME_MIN_FONT_PX,
        min(NAME_MAX_FONT_PX, CONTENT_WIDTH / (len(project.name) * SERIF_CHAR_WIDTH)),
    )
    right = CARD_WIDTH - MARGIN_X
    stars = fmt_int(project.stars)
    noun = "commit" if project.commits == 1 else "commits"
    star_x = right - len(stars) * CAPTION_FONT_PX * MONO_CHAR_WIDTH - STAR_RADIUS - 6
    star_count = (
        _star(star_x, CAPTION_BASELINE - 4, STAR_RADIUS)
        + f'<text class="mono muted" x="{right}" y="{CAPTION_BASELINE}" '
        f'font-size="{CAPTION_FONT_PX}" text-anchor="end">{stars}</text>'
        if project.stars
        else ""
    )
    language = (
        f'<text class="mono muted" x="{right}" y="58" font-size="11" '
        f'text-anchor="end">{esc(project.language)}</text>'
        if project.language
        else ""
    )
    body = (
        card_rect(CARD_WIDTH, CARD_HEIGHT)
        + f'<text class="cap accent" x="{MARGIN_X}" y="58">{index:02d}</text>'
        + language
        + f'<text class="serif ink" x="{MARGIN_X - 1}" y="118" '
        f'font-size="{name_px:.1f}" style="letter-spacing:-.02em">'
        f"{esc(project.name)}</text>"
        + _blurb(project.blurb)
        + _sparkline(project.weekly_commits)
        + f'<text class="mono muted" x="{MARGIN_X}" y="{CAPTION_BASELINE}" '
        f'font-size="{CAPTION_FONT_PX}">{fmt_int(project.commits)} {noun} · 12 weeks'
        "</text>" + star_count
    )
    return document(
        CARD_WIDTH,
        CARD_HEIGHT,
        body,
        title=project.name,
        description=(
            f"{project.name}: {project.blurb} {project.commits} commits in the last "
            f"12 weeks, {project.stars} stars."
        ),
        fonts=("serif", "mono", "sans"),
    )

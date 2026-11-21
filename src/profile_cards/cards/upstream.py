"""Upstream card: pull requests sent to other people's public projects."""

from __future__ import annotations

from dataclasses import dataclass

from profile_cards.config import Config
from profile_cards.model import Snapshot
from profile_cards.theme import (
    card_rect,
    compact,
    delay,
    document,
    esc,
    fmt_int,
)

WIDTH = 880
HEIGHT = 256
MARGIN_X = 36
TILE_TOP = 96
TILE_HEIGHT = 118
TILE_GAP = 14
TILE_RADIUS = 20
TILE_PAD = 22
FOOTER_BASELINE = 242
FOOTER_REPOS = 3


@dataclass(frozen=True)
class Tile:
    label: str
    value: str
    caption: str
    fill_class: str
    text_class: str
    text_fill: str | None = None


def _tile(index: int, tile: Tile, tile_width: float) -> str:
    x = MARGIN_X + index * (tile_width + TILE_GAP)

    def paint(font_class: str) -> str:
        classes = f"{font_class} {tile.text_class}".strip()
        fill = f' fill="{tile.text_fill}"' if tile.text_fill else ""
        return f'class="{classes}"{fill}'

    return (
        f'<g class="rise" {delay(0.1 + index * 0.12)}>'
        f'<rect class="{tile.fill_class}" x="{x:.1f}" y="{TILE_TOP}" '
        f'width="{tile_width:.1f}" height="{TILE_HEIGHT}" rx="{TILE_RADIUS}"/>'
        f'<text {paint("cap")} x="{x + TILE_PAD:.1f}" y="{TILE_TOP + 30}" '
        f'font-size="11" opacity=".8">{esc(tile.label)}</text>'
        f'<text {paint("serif")} x="{x + TILE_PAD:.1f}" y="{TILE_TOP + 86}" '
        f'font-size="64" style="letter-spacing:-.02em">{esc(tile.value)}</text>'
        f'<text {paint("sans")} x="{x + TILE_PAD + 1:.1f}" y="{TILE_TOP + 106}" '
        f'font-size="12.5" opacity=".85">{esc(tile.caption)}</text></g>'
    )


def render(config: Config, snapshot: Snapshot) -> str:
    upstream = snapshot.upstream
    tiles = (
        Tile(
            "Merged",
            fmt_int(upstream.merged_prs),
            "pull requests in projects I don't own",
            "solid",
            "",
            "#fff",
        ),
        Tile(
            "In review",
            fmt_int(upstream.open_prs),
            "open pull requests right now",
            "ink",
            "paper",
        ),
        Tile(
            "Reach",
            compact(upstream.reach),
            "stars across the projects I shipped to",
            "t1",
            "ink",
        ),
    )
    tile_width = (WIDTH - 2 * MARGIN_X - 2 * TILE_GAP) / len(tiles)
    names = [repo.name for repo in upstream.repos[:FOOTER_REPOS]]
    extra = len(upstream.repos) - FOOTER_REPOS
    if extra > 0:
        names.append(f"+{extra} more")
    footer = " · ".join(names)
    body = (
        card_rect(WIDTH, HEIGHT)
        + f'<text class="serif ink" x="{MARGIN_X}" y="76" font-size="44" '
        f'style="letter-spacing:-.02em">Shipped <tspan class="it accent">upstream'
        "</tspan></text>"
        + f'<text class="cap muted" x="{WIDTH - MARGIN_X}" y="66" text-anchor="end">'
        "Public projects only</text>"
        + "".join(_tile(i, tile, tile_width) for i, tile in enumerate(tiles))
        + (
            f'<text class="mono muted" x="{MARGIN_X}" y="{FOOTER_BASELINE}" '
            f'font-size="11">{esc(footer)}</text>'
            if footer
            else ""
        )
    )
    return document(
        WIDTH,
        HEIGHT,
        body,
        title="Open-source contributions",
        description=(
            f"{config.login} has {upstream.merged_prs} merged and {upstream.open_prs} "
            f"open pull requests in public projects owned by others."
        ),
        fonts=("serif", "serif-italic", "mono", "sans"),
    )

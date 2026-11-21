"""Heatmap card: every day of the year as a square, in five blues."""

from __future__ import annotations

from profile_cards.config import Config
from profile_cards.model import Snapshot
from profile_cards.stats import (
    DAYS_PER_WEEK,
    LEVELS,
    MONTH_NAMES,
    Cell,
    grid,
    level_for,
    quantile_thresholds,
)
from profile_cards.theme import card_rect, delay, document, esc, fmt_int, live_dot

WIDTH = 880
HEIGHT = 316
LEGEND_OFFSET = 44
LEGEND_SWATCH_GAP = 4
LEGEND_MORE_WIDTH = 40
MARGIN_X = 36
GRID_TOP = 124
CELL = 11.6
PITCH = 15.0
CELL_RADIUS = 3
WAVE_SECONDS_PER_WEEK = 0.012
MONTH_LABEL_MIN_GAP = 3
CAP_CHAR_WIDTH = 8.9
UPDATED_FORMAT = "%d %b %Y"


def _cells(cells: list[Cell], thresholds: tuple[int, ...], today_key: object) -> str:
    out = []
    for cell in cells:
        level = level_for(cell.day.count, thresholds)
        cls = "empty" if level == 0 else f"t{level}"
        x = MARGIN_X + cell.column * PITCH
        y = GRID_TOP + cell.row * PITCH
        out.append(
            f'<rect class="{cls} pop" x="{x:.1f}" y="{y:.1f}" width="{CELL}" '
            f'height="{CELL}" rx="{CELL_RADIUS}" '
            f"{delay(cell.column * WAVE_SECONDS_PER_WEEK)}/>"
        )
        if cell.day.date == today_key:
            out.append(
                f'<rect class="line live" x="{x - 2:.1f}" y="{y - 2:.1f}" '
                f'width="{CELL + 4}" height="{CELL + 4}" rx="{CELL_RADIUS + 1}" '
                f'stroke-width="1.5" style="stroke:var(--accent)"/>'
            )
    return "".join(out)


def _month_labels(cells: list[Cell]) -> str:
    """A label under the first column of each month, skipping crowded ones."""
    labels: list[tuple[int, str]] = []
    seen: set[tuple[int, int]] = set()
    for cell in cells:
        key = (cell.day.date.year, cell.day.date.month)
        if key not in seen and cell.day.date.day <= DAYS_PER_WEEK:
            seen.add(key)
            labels.append((cell.column, MONTH_NAMES[key[1] - 1]))
    out = []
    last_column = -MONTH_LABEL_MIN_GAP
    for column, name in labels:
        if column - last_column < MONTH_LABEL_MIN_GAP:
            continue
        last_column = column
        out.append(
            f'<text class="mono muted" x="{MARGIN_X + column * PITCH:.1f}" '
            f'y="{GRID_TOP + DAYS_PER_WEEK * PITCH + 16}" font-size="11">{name}</text>'
        )
    return "".join(out)


def _legend(y: float) -> str:
    """'less [squares] more', right-aligned on its own row under the month labels."""
    right = WIDTH - MARGIN_X
    swatch_pitch = CELL + LEGEND_SWATCH_GAP
    first_swatch = right - LEGEND_MORE_WIDTH - (LEVELS + 1) * swatch_pitch
    swatches = []
    for i in range(LEVELS + 1):
        cls = "empty" if i == 0 else f"t{i}"
        swatches.append(
            f'<rect class="{cls}" x="{first_swatch + i * swatch_pitch:.1f}" '
            f'y="{y - 10}" width="{CELL}" height="{CELL}" rx="{CELL_RADIUS}"/>'
        )
    return (
        f'<text class="mono muted" x="{first_swatch - 8:.1f}" y="{y}" '
        f'font-size="11" text-anchor="end">less</text>'
        + "".join(swatches)
        + f'<text class="mono muted" x="{right}" y="{y}" font-size="11" '
        f'text-anchor="end">more</text>'
    )


def render(config: Config, snapshot: Snapshot) -> str:
    cells = grid(snapshot.days)
    thresholds = quantile_thresholds(c.day.count for c in cells)
    updated = snapshot.generated.strftime(UPDATED_FORMAT).upper()
    right = WIDTH - MARGIN_X
    refreshed = "Refreshed daily"
    dot_x = right - len(refreshed) * CAP_CHAR_WIDTH - 14
    body = (
        card_rect(WIDTH, HEIGHT)
        + f'<text class="serif ink" x="{MARGIN_X}" y="76" font-size="44" '
        f'style="letter-spacing:-.02em">Every day, '
        f'<tspan class="it accent">in blue</tspan></text>'
        + live_dot(dot_x, 62)
        + f'<text class="cap muted" x="{right}" y="66" text-anchor="end">'
        f"{refreshed}</text>"
        + f'<text class="cap muted" x="{right}" y="86" text-anchor="end" '
        f'font-size="10">Updated {esc(updated)}</text>'
        + _cells(cells, thresholds, snapshot.days[-1].date if snapshot.days else None)
        + _month_labels(cells)
        + _legend(GRID_TOP + DAYS_PER_WEEK * PITCH + LEGEND_OFFSET)
    )
    return document(
        WIDTH,
        HEIGHT,
        body,
        title="Contribution heatmap",
        description=(
            f"{config.login}'s {fmt_int(snapshot.total)} GitHub contributions over the "
            "last year, one square per day, darker blue for busier days."
        ),
        fonts=("serif", "serif-italic", "mono"),
    )

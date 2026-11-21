"""Activity card: the year in numbers, monthly bars, streaks and weekday rhythm."""

from __future__ import annotations

from profile_cards.config import Config
from profile_cards.model import Snapshot
from profile_cards.stats import (
    MONTH_NAMES,
    MonthTotal,
    active_days,
    busiest_day,
    month_totals,
    streaks,
    weekday_totals,
)
from profile_cards.theme import card_rect, delay, document, esc, fmt_int, live_dot

WIDTH = 880
HEIGHT = 448
MARGIN_X = 36
CHART_RIGHT = 560
BASELINE = 392
MAX_BAR_HEIGHT = 170
MIN_BAR_HEIGHT = 4
BAR_WIDTH = 30
BAR_RADIUS = 7
BAR_STAGGER_SECONDS = 0.06
BAR_FIRST_DELAY_SECONDS = 0.15
SIDE_X = 612
SIDE_WIDTH = 232
STAT_ROW_HEIGHT = 68
STAT_FIRST_BASELINE = 214
STAT_RULE_OFFSET = 38
RHYTHM_BASELINE = 430
RHYTHM_MAX_HEIGHT = 24
RHYTHM_BAR_WIDTH = 24
WEEKDAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
HATCH = (
    '<defs><pattern id="hatch" width="7" height="7" patternUnits="userSpaceOnUse" '
    'patternTransform="rotate(45)"><rect width="3.5" height="7" '
    'style="fill:var(--l4)"/></pattern></defs>'
)


def _bars(months: list[MonthTotal]) -> str:
    peak = max((m.total for m in months), default=0) or 1
    full = [m.total for m in months if not m.partial]
    average = sum(full) / len(full) if full else 0
    pitch = (CHART_RIGHT - MARGIN_X) / len(months)
    peak_index = max(range(len(months)), key=lambda i: months[i].total)
    out = [
        f'<line class="line" x1="{MARGIN_X}" x2="{CHART_RIGHT}" y1="{BASELINE}" '
        f'y2="{BASELINE}" stroke-width="1"/>'
    ]
    for i, month in enumerate(months):
        height = max(MIN_BAR_HEIGHT, month.total / peak * MAX_BAR_HEIGHT)
        x = MARGIN_X + i * pitch + (pitch - BAR_WIDTH) / 2
        cls = "grow" if month.partial else f"grow t{5 if i == peak_index else 4}"
        paint = "fill:url(#hatch);" if month.partial else ""
        out.append(
            f'<rect class="{cls}" x="{x:.1f}" y="{BASELINE - height:.1f}" '
            f'width="{BAR_WIDTH}" height="{height:.1f}" rx="{BAR_RADIUS}" '
            f'style="{paint}animation-delay:{_grow_seconds(i):.2f}s"/>'
        )
        out.append(
            f'<text class="mono muted" x="{x + BAR_WIDTH / 2:.1f}" y="{BASELINE + 22}" '
            f'font-size="11" text-anchor="middle">{month.label}</text>'
        )
        if i == peak_index and month.total:
            out.append(
                f'<text class="mono accent rise" x="{x + BAR_WIDTH / 2:.1f}" '
                f'y="{BASELINE - height - 9:.1f}" font-size="12" text-anchor="middle" '
                f"{delay(0.9)}>{fmt_int(month.total)}</text>"
            )
    if average:
        y = BASELINE - average / peak * MAX_BAR_HEIGHT
        out.append(
            f'<line class="line" x1="{MARGIN_X}" x2="{CHART_RIGHT}" y1="{y:.1f}" '
            f'y2="{y:.1f}" stroke-width="1.2" stroke-dasharray="3 6"/>'
            f'<text class="mono muted" x="{MARGIN_X}" y="{y - 6:.1f}" '
            f'font-size="10">avg {fmt_int(round(average))} / month</text>'
        )
    return "".join(out)


def _grow_seconds(index: int) -> float:
    return BAR_FIRST_DELAY_SECONDS + index * BAR_STAGGER_SECONDS


def _stat(row: int, number: str, unit: str, caption: str) -> str:
    base = STAT_FIRST_BASELINE + row * STAT_ROW_HEIGHT
    rule = (
        f'<line class="line" x1="{SIDE_X}" x2="{SIDE_X + SIDE_WIDTH}" '
        f'y1="{base - STAT_RULE_OFFSET}" y2="{base - STAT_RULE_OFFSET}" '
        f'stroke-width="1"/>'
        if row
        else ""
    )
    return (
        rule + f'<text class="serif ink rise" x="{SIDE_X}" y="{base}" font-size="44" '
        f"{delay(0.2 + row * 0.12)}>{esc(number)}"
        f'<tspan class="it muted" font-size="24">{esc(unit)}</tspan></text>'
        f'<text class="mono muted" x="{SIDE_X}" y="{base + 20}" font-size="11">'
        f"{esc(caption)}</text>"
    )


def _rhythm(totals: list[int]) -> str:
    peak = max(totals) or 1
    best = totals.index(max(totals))
    pitch = (SIDE_WIDTH - RHYTHM_BAR_WIDTH) / 6
    bars = []
    for i, total in enumerate(totals):
        height = max(MIN_BAR_HEIGHT, total / peak * RHYTHM_MAX_HEIGHT)
        cls = "solid" if i == best else "t2"
        bars.append(
            f'<rect class="grow {cls}" x="{SIDE_X + i * pitch:.1f}" '
            f'y="{RHYTHM_BASELINE - height:.1f}" width="{RHYTHM_BAR_WIDTH}" '
            f'height="{height:.1f}" rx="5" {delay(0.5 + i * 0.05)}/>'
        )
    return (
        f'<text class="mono muted" x="{SIDE_X}" y="{RHYTHM_BASELINE - 38}" '
        f'font-size="11">Busiest on {WEEKDAYS[best]}s</text>' + "".join(bars)
    )


def render(config: Config, snapshot: Snapshot) -> str:
    months = month_totals(snapshot.days, snapshot.generated)
    run = streaks(snapshot.days, snapshot.generated)
    peak_day = busiest_day(snapshot.days)
    notes = []
    if snapshot.private_contributions:
        notes.append(
            f"{fmt_int(snapshot.private_contributions)} of them in private "
            "repositories."
        )
    if peak_day and peak_day.count:
        notes.append(
            f"Busiest day: {fmt_int(peak_day.count)} on "
            f"{peak_day.date.day} {MONTH_NAMES[peak_day.date.month - 1]}."
        )
    body = (
        card_rect(WIDTH, HEIGHT)
        + HATCH
        + live_dot(MARGIN_X + 4, 62)
        + f'<text class="cap muted" x="{MARGIN_X + 18}" y="66">'
        "The last 12 months on GitHub</text>"
        + f'<text class="serif ink" x="{MARGIN_X - 2}" y="146" font-size="82" '
        f'style="letter-spacing:-.025em">{fmt_int(snapshot.total)}'
        f'<tspan class="it accent"> contributions</tspan></text>'
        + f'<text class="sans muted" x="{MARGIN_X}" y="176" font-size="14">'
        f"{esc(' '.join(notes))}</text>"
        + _bars(months)
        + _stat(0, str(run.current), " days", "current streak")
        + _stat(1, str(run.longest), " days", "longest streak")
        + _stat(
            2,
            str(active_days(snapshot.days)),
            f" / {len(snapshot.days)}",
            "days with a contribution",
        )
        + _rhythm(weekday_totals(snapshot.days))
    )
    return document(
        WIDTH,
        HEIGHT,
        body,
        title="Twelve months of GitHub activity",
        description=(
            f"{config.login} made {fmt_int(snapshot.total)} contributions in the last "
            f"12 months. Current streak {run.current} days, longest {run.longest}."
        ),
        fonts=("serif", "serif-italic", "mono", "sans"),
    )

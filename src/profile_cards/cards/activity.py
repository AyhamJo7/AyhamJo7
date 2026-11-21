"""Activity card: two years in one chart, plus streaks and weekday rhythm.

With two full years of data it shows 24 monthly bars, the earlier twelve in a lighter
blue; with only one year it shows twelve.
"""

from __future__ import annotations

from datetime import date

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
from profile_cards.theme import (
    SANS_CHAR_WIDTH,
    card_rect,
    delay,
    document,
    esc,
    fmt_int,
    live_dot,
)

WIDTH = 880
HEIGHT = 448
MARGIN_X = 36
CHART_RIGHT = 560
BASELINE = 392
MAX_BAR_HEIGHT = 150
MIN_BAR_HEIGHT = 4
BAR_WIDTH = 30
BAR_FILL = 0.66
BAR_RADIUS = 7
MIN_BAR_RADIUS = 3
LATEST_MONTHS = 12
WIDE_PITCH = 40
BAR_TOTAL_STAGGER_SECONDS = 0.8
BAR_FIRST_DELAY_SECONDS = 0.15
YEAR_CAPTION_OFFSET = 36
YEAR_CAPTION_MIN_GAP = 4
EN_DASH = "–"  # noqa: RUF001 - the typographic range dash is intended
NOTE_BASELINES = (176, 198)
LEGEND_DOT_RADIUS = 4.5
LEGEND_TEXT_GAP = 8
LEGEND_ITEM_GAP = 26
LEGEND_FONT_PX = 14
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


def _bar_class(
    index: int, month: MonthTotal, peak_index: int, earlier_count: int
) -> str:
    if month.partial:
        return "grow"
    if index == peak_index:
        return "grow t5"
    return "grow t2" if index < earlier_count else "grow t4"


def _shows_year(months: list[MonthTotal], index: int) -> bool:
    """A year caption sits under every January, and under the first bar only if there
    is room before the first January (otherwise two captions would collide)."""
    if months[index].month == 1:
        return True
    if index != 0:
        return False
    first_january = next((i for i, m in enumerate(months) if m.month == 1), None)
    return first_january is not None and first_january >= YEAR_CAPTION_MIN_GAP


def _bars(months: list[MonthTotal]) -> str:
    earlier_count = max(0, len(months) - LATEST_MONTHS)
    peak = max((m.total for m in months), default=0) or 1
    full = [m.total for m in months if not m.partial]
    average = sum(full) / len(full) if full else 0
    pitch = (CHART_RIGHT - MARGIN_X) / len(months)
    bar_width = min(BAR_WIDTH, pitch * BAR_FILL)
    radius = max(MIN_BAR_RADIUS, min(BAR_RADIUS, bar_width / 2.2))
    label_px = 11 if pitch >= WIDE_PITCH else 9
    stagger = BAR_TOTAL_STAGGER_SECONDS / len(months)
    peak_index = max(range(len(months)), key=lambda i: months[i].total)
    out = [
        f'<line class="line" x1="{MARGIN_X}" x2="{CHART_RIGHT}" y1="{BASELINE}" '
        f'y2="{BASELINE}" stroke-width="1"/>'
    ]
    for i, month in enumerate(months):
        height = max(MIN_BAR_HEIGHT, month.total / peak * MAX_BAR_HEIGHT)
        x = MARGIN_X + i * pitch + (pitch - bar_width) / 2
        cls = _bar_class(i, month, peak_index, earlier_count)
        paint = "fill:url(#hatch);" if month.partial else ""
        grow_delay = BAR_FIRST_DELAY_SECONDS + i * stagger
        out.append(
            f'<rect class="{cls}" x="{x:.1f}" y="{BASELINE - height:.1f}" '
            f'width="{bar_width:.1f}" height="{height:.1f}" rx="{radius:.1f}" '
            f'style="{paint}animation-delay:{grow_delay:.2f}s"/>'
        )
        out.append(
            f'<text class="mono muted" x="{x + bar_width / 2:.1f}" '
            f'y="{BASELINE + 22}" font-size="{label_px}" text-anchor="middle">'
            f"{month.label}</text>"
        )
        if earlier_count and _shows_year(months, i):
            out.append(
                f'<text class="mono muted" x="{x:.1f}" '
                f'y="{BASELINE + YEAR_CAPTION_OFFSET}" font-size="10">'
                f"{month.year}</text>"
            )
        if i == peak_index and month.total:
            out.append(
                f'<text class="mono accent rise" x="{x + bar_width / 2:.1f}" '
                f'y="{BASELINE - height - 9:.1f}" font-size="12" text-anchor="middle" '
                f"{delay(0.9)}>{fmt_int(month.total)}</text>"
            )
    if average:
        y = BASELINE - average / peak * MAX_BAR_HEIGHT
        out.append(
            f'<line class="line" x1="{MARGIN_X}" x2="{CHART_RIGHT}" y1="{y:.1f}" '
            f'y2="{y:.1f}" stroke-width="1.2" stroke-dasharray="3 6"/>'
            f'<text class="mono muted" x="{CHART_RIGHT + 6}" y="{y + 3.5:.1f}" '
            f'font-size="10">avg {fmt_int(round(average))}</text>'
        )
    return "".join(out)


def _legend(items: list[tuple[str, str]], baseline: int) -> str:
    """Coloured dots with text, where each dot repeats the colour of its bars."""
    x = float(MARGIN_X)
    out = []
    for cls, text in items:
        dot_x = x + LEGEND_DOT_RADIUS
        text_x = x + 2 * LEGEND_DOT_RADIUS + LEGEND_TEXT_GAP
        out.append(
            f'<circle class="{cls}" cx="{dot_x:.1f}" cy="{baseline - 5}" '
            f'r="{LEGEND_DOT_RADIUS}"/>'
            f'<text class="sans muted" x="{text_x:.1f}" y="{baseline}" '
            f'font-size="{LEGEND_FONT_PX}">{esc(text)}</text>'
        )
        x = text_x + len(text) * LEGEND_FONT_PX * SANS_CHAR_WIDTH + LEGEND_ITEM_GAP
    return "".join(out)


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


def _date_label(day: date) -> str:
    return f"{day.day} {MONTH_NAMES[day.month - 1]} {day.year}"


def render(config: Config, snapshot: Snapshot) -> str:
    two_years = snapshot.has_previous_year
    days = snapshot.window(1) + snapshot.window(0) if two_years else snapshot.window(0)
    end = snapshot.generated
    span_months = 2 * LATEST_MONTHS if two_years else LATEST_MONTHS
    total = sum(day.count for day in days)
    latest_total = snapshot.total
    previous_total = total - latest_total
    # Streaks look at all the history, not only the days shown, so a streak that began
    # earlier is counted in full.
    run = streaks(snapshot.days, end)
    months = month_totals(days, end, months=span_months)
    peak_day = busiest_day(days)
    private = snapshot.private_contributions + (
        snapshot.private_contributions_previous if two_years else 0
    )

    notes = []
    if private:
        notes.append(f"{fmt_int(private)} of them in private repositories.")
    if peak_day and peak_day.count:
        notes.append(
            f"Busiest day: {fmt_int(peak_day.count)} on "
            f"{peak_day.date.day} {MONTH_NAMES[peak_day.date.month - 1]}."
        )
    note_text = " ".join(notes)
    if two_years:
        lines = _legend(
            [
                ("t4", f"{fmt_int(latest_total)} in the last 12 months"),
                ("t2", f"{fmt_int(previous_total)} in the 12 months before"),
            ],
            NOTE_BASELINES[0],
        ) + (
            f'<text class="sans muted" x="{MARGIN_X}" y="{NOTE_BASELINES[1]}" '
            f'font-size="14">{esc(note_text)}</text>'
        )
    else:
        lines = (
            f'<text class="sans muted" x="{MARGIN_X}" y="{NOTE_BASELINES[0]}" '
            f'font-size="14">{esc(note_text)}</text>'
        )

    eyebrow = f"The last {span_months} months on GitHub"
    start = days[0].date if days else end
    body = (
        card_rect(WIDTH, HEIGHT)
        + HATCH
        + live_dot(MARGIN_X + 4, 62)
        + f'<text class="cap muted" x="{MARGIN_X + 18}" y="66">{esc(eyebrow)}</text>'
        + f'<text class="mono muted" x="{WIDTH - MARGIN_X}" y="66" font-size="11" '
        f'text-anchor="end">{_date_label(start)} {EN_DASH} {_date_label(end)}</text>'
        + f'<text class="serif ink" x="{MARGIN_X - 2}" y="146" font-size="82" '
        f'style="letter-spacing:-.025em">{fmt_int(total)}'
        f'<tspan class="it accent"> contributions</tspan></text>'
        + lines
        + _bars(months)
        + _stat(0, str(run.current), " days", "current streak")
        + _stat(1, str(run.longest), " days", "longest streak")
        + _stat(
            2,
            str(active_days(days)),
            f" / {len(days)}",
            "days with a contribution",
        )
        + _rhythm(weekday_totals(days))
    )
    split = (
        f": {fmt_int(latest_total)} in the last 12 months and "
        f"{fmt_int(previous_total)} in the 12 months before"
        if two_years
        else ""
    )
    return document(
        WIDTH,
        HEIGHT,
        body,
        title=f"{span_months} months of GitHub activity",
        description=(
            f"{config.login} made {fmt_int(total)} contributions between "
            f"{_date_label(start)} and {_date_label(end)}{split}. Current streak "
            f"{run.current} days, longest streak {run.longest} days."
        ),
        fonts=("serif", "serif-italic", "mono", "sans"),
    )

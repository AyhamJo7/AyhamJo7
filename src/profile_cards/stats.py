"""Pure statistics over a year of daily contribution counts."""

from __future__ import annotations

import calendar
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from profile_cards.model import Day

LEVELS = 5
MONTHS_SHOWN = 12
DAYS_PER_WEEK = 7
MONTH_NAMES = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)
WEEKDAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


@dataclass(frozen=True)
class MonthTotal:
    year: int
    month: int
    total: int
    partial: bool

    @property
    def label(self) -> str:
        return MONTH_NAMES[self.month - 1]


@dataclass(frozen=True)
class Streaks:
    current: int
    longest: int


@dataclass(frozen=True)
class Cell:
    day: Day
    column: int
    row: int


def quantile_thresholds(counts: Iterable[int], levels: int = LEVELS) -> tuple[int, ...]:
    """Upper bounds of levels 1..levels-1, taken from the non-zero counts."""
    nonzero = sorted(count for count in counts if count > 0)
    if not nonzero:
        return ()
    return tuple(
        nonzero[math.ceil(len(nonzero) * step / levels) - 1]
        for step in range(1, levels)
    )


def level_for(count: int, thresholds: Sequence[int]) -> int:
    """0 for no activity, otherwise 1..LEVELS by quantile."""
    if count <= 0:
        return 0
    return 1 + sum(count > bound for bound in thresholds)


def month_totals(
    days: Sequence[Day], today: date, months: int = MONTHS_SHOWN
) -> list[MonthTotal]:
    """Totals for the last `months` calendar months, ending with today's month."""
    keys: list[tuple[int, int]] = []
    year, month = today.year, today.month
    for _ in range(months):
        keys.append((year, month))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    keys.reverse()
    sums = dict.fromkeys(keys, 0)
    for day in days:
        key = (day.date.year, day.date.month)
        if key in sums:
            sums[key] += day.count
    month_length = calendar.monthrange(today.year, today.month)[1]
    return [
        MonthTotal(
            y,
            m,
            sums[(y, m)],
            partial=(y, m) == (today.year, today.month) and today.day < month_length,
        )
        for y, m in keys
    ]


def streaks(days: Sequence[Day], today: date) -> Streaks:
    """Current streak (it survives an empty today) and the longest in the range."""
    counts = {day.date: day.count for day in days}
    cursor = today if counts.get(today, 0) > 0 else today - timedelta(days=1)
    current = 0
    while counts.get(cursor, 0) > 0:
        current += 1
        cursor -= timedelta(days=1)

    longest = run = 0
    previous: date | None = None
    for day in sorted(days, key=lambda d: d.date):
        if previous is not None and day.date - previous != timedelta(days=1):
            run = 0
        run = run + 1 if day.count > 0 else 0
        longest = max(longest, run)
        previous = day.date
    return Streaks(current, longest)


def busiest_day(days: Sequence[Day]) -> Day | None:
    """The day with the most contributions; the latest wins a tie."""
    return max(days, key=lambda d: (d.count, d.date), default=None)


def active_days(days: Sequence[Day]) -> int:
    return sum(1 for day in days if day.count > 0)


def weekday_totals(days: Sequence[Day]) -> list[int]:
    """Contributions per weekday, Monday first."""
    totals = [0] * DAYS_PER_WEEK
    for day in days:
        totals[day.date.weekday()] += day.count
    return totals


def grid(days: Sequence[Day]) -> list[Cell]:
    """Place days on a week-by-weekday grid, Sunday first like GitHub."""
    ordered = sorted(days, key=lambda d: d.date)
    if not ordered:
        return []
    first = ordered[0].date
    start = first - timedelta(days=(first.weekday() + 1) % DAYS_PER_WEEK)
    return [
        Cell(
            day,
            column=(day.date - start).days // DAYS_PER_WEEK,
            row=(day.date.weekday() + 1) % DAYS_PER_WEEK,
        )
        for day in ordered
    ]

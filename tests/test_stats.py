from __future__ import annotations

from datetime import date, timedelta

from profile_cards.model import Day
from profile_cards.stats import (
    LEVELS,
    active_days,
    busiest_day,
    grid,
    level_for,
    month_totals,
    quantile_thresholds,
    streaks,
    weekday_totals,
)

TODAY = date(2026, 11, 21)


def days_from(counts: list[int], end: date = TODAY) -> list[Day]:
    start = end - timedelta(days=len(counts) - 1)
    return [Day(start + timedelta(days=i), c) for i, c in enumerate(counts)]


def test_thresholds_empty_input_has_no_bounds() -> None:
    assert quantile_thresholds([]) == ()
    assert quantile_thresholds([0, 0]) == ()


def test_level_zero_is_no_activity_and_levels_are_monotonic() -> None:
    thresholds = quantile_thresholds(range(1, 101))
    levels = [level_for(c, thresholds) for c in range(0, 101)]
    assert levels[0] == 0
    assert levels == sorted(levels)
    assert max(levels) == LEVELS
    assert min(levels[1:]) == 1


def test_level_for_single_value_is_lowest_level() -> None:
    assert level_for(5, quantile_thresholds([5, 5, 5])) == 1


def test_month_totals_covers_twelve_months_and_flags_the_current_one() -> None:
    days = days_from([1] * 365)
    months = month_totals(days, TODAY)
    assert len(months) == 12
    assert (months[0].year, months[0].month) == (2025, 12)
    assert (months[-1].year, months[-1].month) == (2026, 11)
    assert [m.partial for m in months] == [False] * 11 + [True]
    assert months[-1].total == 21
    assert months[0].label == "Dec"


def test_the_anchor_month_is_partial_only_before_its_last_day() -> None:
    mid_month = month_totals(
        days_from([1] * 400, date(2026, 11, 21)), date(2026, 11, 21)
    )
    assert mid_month[-1].partial

    month_end = date(2025, 11, 30)
    complete = month_totals(days_from([1] * 400, month_end), month_end)
    assert not complete[-1].partial
    assert complete[-1].total == 30
    assert not any(month.partial for month in complete)


def test_streak_survives_an_empty_today() -> None:
    days = days_from([0, 1, 1, 1, 0])
    assert streaks(days, TODAY).current == 3


def test_streak_counts_today_when_active() -> None:
    assert streaks(days_from([0, 1, 1]), TODAY).current == 2


def test_streak_is_zero_after_two_empty_days() -> None:
    assert streaks(days_from([1, 1, 0, 0]), TODAY).current == 0


def test_longest_streak_is_found_anywhere_in_the_range() -> None:
    days = days_from([1, 1, 1, 1, 0, 1, 1, 0, 1])
    assert streaks(days, TODAY).longest == 4


def test_longest_streak_breaks_on_missing_dates() -> None:
    days = [Day(date(2026, 1, 1), 1), Day(date(2026, 1, 3), 1)]
    assert streaks(days, TODAY).longest == 1


def test_busiest_day_prefers_the_latest_on_a_tie() -> None:
    days = days_from([5, 9, 9, 2])
    assert busiest_day(days) == days[2]
    assert busiest_day([]) is None


def test_active_days_counts_non_zero_days() -> None:
    assert active_days(days_from([0, 3, 0, 1])) == 2


def test_weekday_totals_start_on_monday() -> None:
    monday = Day(date(2026, 11, 16), 4)
    sunday = Day(date(2026, 11, 22), 2)
    totals = weekday_totals([monday, sunday])
    assert totals[0] == 4
    assert totals[6] == 2


def test_grid_places_sunday_in_row_zero_and_starts_a_column_on_sunday() -> None:
    saturday = Day(date(2026, 11, 21), 1)
    sunday = Day(date(2026, 11, 22), 1)
    monday = Day(date(2026, 11, 23), 1)
    cells = {c.day.date: c for c in grid([saturday, sunday, monday])}
    assert cells[saturday.date].row == 6
    assert cells[sunday.date].row == 0
    assert cells[monday.date].row == 1
    assert cells[sunday.date].column == cells[saturday.date].column + 1
    assert cells[monday.date].column == cells[sunday.date].column


def test_grid_of_nothing_is_empty() -> None:
    assert grid([]) == []

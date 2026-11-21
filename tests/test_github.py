from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from profile_cards import github
from profile_cards.config import ProjectConfig
from profile_cards.github import (
    GitHubError,
    parse_calendar,
    parse_commit_activity,
    parse_upstream,
    streak_reaches_history_start,
)
from profile_cards.model import COMMIT_WEEKS, YEAR_DAYS, Day


def year_payload(
    private: int, days: list[tuple[str, int]], *, split: int = 2
) -> dict[str, Any]:
    """One `contributionsCollection`, with its days spread over two weeks."""
    return {
        "restrictedContributionsCount": private,
        "contributionCalendar": {
            "weeks": [
                {
                    "contributionDays": [
                        {"date": d, "contributionCount": c} for d, c in days[:split]
                    ]
                },
                {
                    "contributionDays": [
                        {"date": d, "contributionCount": c} for d, c in days[split:]
                    ]
                },
            ]
        },
    }


def calendar_payload() -> dict[str, Any]:
    return {
        "user": {
            "current": year_payload(
                7, [("2026-11-02", 3), ("2026-11-01", 0), ("2026-11-03", 5)]
            ),
            "previous": year_payload(11, [("2025-11-02", 2), ("2025-11-01", 4)]),
        }
    }


def search_payload() -> dict[str, Any]:
    def node(name: str, stars: int, private: bool) -> dict[str, Any]:
        return {
            "repository": {
                "nameWithOwner": name,
                "stargazerCount": stars,
                "isPrivate": private,
            }
        }

    return {
        "merged": {
            "nodes": [
                node("a/small", 10, False),
                node("b/big", 900, False),
                node("b/big", 900, False),
                node("hidden/secret", 5000, True),
                {},
            ]
        },
        "open": {"issueCount": 4},
    }


def test_both_years_are_merged_sorted_and_each_private_count_is_read() -> None:
    days, private, private_previous = parse_calendar(calendar_payload())
    assert [d.date.isoformat() for d in days] == [
        "2025-11-01",
        "2025-11-02",
        "2026-11-01",
        "2026-11-02",
        "2026-11-03",
    ]
    assert [d.count for d in days] == [4, 2, 0, 3, 5]
    assert (private, private_previous) == (7, 11)


def active_days(length: int, today: date = date(2026, 11, 21)) -> tuple[Day, ...]:
    start = today - timedelta(days=length - 1)
    return tuple(Day(start + timedelta(days=i), 1) for i in range(length))


def test_older_years_are_only_needed_while_the_streak_reaches_the_oldest_day() -> None:
    today = date(2026, 11, 21)
    assert streak_reaches_history_start(active_days(730), today)
    assert not streak_reaches_history_start((), today)

    broken = list(active_days(730))
    broken[300] = Day(broken[300].date, 0)
    assert not streak_reaches_history_start(tuple(broken), today)


def test_history_is_extended_until_the_streak_breaks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    today = date(2026, 11, 21)
    requests: list[str] = []

    def fake_graphql(
        _query: str, variables: dict[str, Any], _token: str
    ) -> dict[str, Any]:
        requests.append(variables["from"])
        start = date.fromisoformat(variables["from"][:10])
        count = 0 if len(requests) == 2 else 1  # the second older year is empty
        days = [(str(start + timedelta(days=i)), count) for i in range(YEAR_DAYS)]
        return {"user": {"contributionsCollection": year_payload(0, days)}}

    monkeypatch.setattr(github, "_graphql", fake_graphql)
    start = github._extend_streak_history("me", "token", today, active_days(730))

    assert len(requests) == 2, "stops once a fetched year breaks the streak"
    assert len(start) == 730 + 2 * YEAR_DAYS


def test_history_extension_stops_at_the_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    today = date(2026, 11, 21)
    calls = 0

    def always_active(
        _query: str, variables: dict[str, Any], _token: str
    ) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        begin = date.fromisoformat(variables["from"][:10])
        days = [(str(begin + timedelta(days=i)), 1) for i in range(YEAR_DAYS)]
        return {"user": {"contributionsCollection": year_payload(0, days)}}

    monkeypatch.setattr(github, "_graphql", always_active)
    github._extend_streak_history("me", "token", today, active_days(730))

    assert calls == github.HISTORY_WINDOWS_MAX - github.HISTORY_WINDOWS_MIN


def test_a_streak_that_already_ended_fetches_nothing_more(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def must_not_be_called(*_a: Any, **_k: Any) -> dict[str, Any]:
        raise AssertionError("no older year should be fetched")

    monkeypatch.setattr(github, "_graphql", must_not_be_called)
    days = list(active_days(730))
    days[400] = Day(days[400].date, 0)
    result = github._extend_streak_history(
        "me", "token", date(2026, 11, 21), tuple(days)
    )
    assert result == tuple(days)


def test_upstream_excludes_private_repositories_and_orders_by_stars() -> None:
    upstream = parse_upstream(search_payload())
    assert upstream.merged_prs == 3
    assert upstream.open_prs == 4
    assert [r.name for r in upstream.repos] == ["b/big", "a/small"]
    assert upstream.repos[0].merged == 2
    assert upstream.reach == 910
    assert all("secret" not in r.name for r in upstream.repos)


def test_commit_activity_keeps_the_last_weeks_oldest_first() -> None:
    payload = [{"total": n} for n in range(30)]
    assert parse_commit_activity(payload) == tuple(range(30 - COMMIT_WEEKS, 30))


def test_commit_activity_pads_short_histories_with_zeros() -> None:
    result = parse_commit_activity([{"total": 4}, {"total": 5}])
    assert len(result) == COMMIT_WEEKS
    assert result[-2:] == (4, 5)
    assert result[0] == 0


@pytest.mark.parametrize("payload", [{}, [], None])
def test_commit_activity_that_is_not_ready_raises(payload: Any) -> None:
    with pytest.raises(GitHubError):
        parse_commit_activity(payload)


def test_commit_activity_retries_while_github_is_computing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    replies = iter([(202, {}), (202, {}), (200, [{"total": 9}])])
    monkeypatch.setattr(github, "_call", lambda *_a, **_k: next(replies))
    monkeypatch.setattr("profile_cards.github.time.sleep", lambda _s: None)
    assert github._fetch_commit_activity("o/r", "token")[-1] == 9


def test_commit_activity_gives_up_after_the_attempt_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def never_ready(*_a: Any, **_k: Any) -> tuple[int, dict[str, Any]]:
        calls.append(1)
        return 202, {}

    monkeypatch.setattr(github, "_call", never_ready)
    monkeypatch.setattr("profile_cards.github.time.sleep", lambda _s: None)
    with pytest.raises(GitHubError):
        github._fetch_commit_activity("o/r", "token")
    assert len(calls) == github.STATS_ATTEMPTS


def test_graphql_errors_are_surfaced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        github, "_call", lambda *_a, **_k: (200, {"errors": [{"message": "boom"}]})
    )
    with pytest.raises(GitHubError):
        github._graphql("query { x }", {}, "token")


def test_private_project_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        github,
        "_graphql",
        lambda *_a, **_k: {"repository": {"isPrivate": True}},
    )
    entry = ProjectConfig("o/r", None)
    with pytest.raises(GitHubError):
        github._fetch_project(entry, "token")

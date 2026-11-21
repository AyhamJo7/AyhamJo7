from __future__ import annotations

from typing import Any

import pytest

from profile_cards import github
from profile_cards.config import ProjectConfig
from profile_cards.github import (
    GitHubError,
    parse_calendar,
    parse_commit_activity,
    parse_upstream,
)
from profile_cards.model import COMMIT_WEEKS


def calendar_payload() -> dict[str, Any]:
    return {
        "user": {
            "contributionsCollection": {
                "restrictedContributionsCount": 7,
                "contributionCalendar": {
                    "weeks": [
                        {
                            "contributionDays": [
                                {"date": "2026-11-02", "contributionCount": 3},
                                {"date": "2026-11-01", "contributionCount": 0},
                            ]
                        },
                        {
                            "contributionDays": [
                                {"date": "2026-11-03", "contributionCount": 5}
                            ]
                        },
                    ]
                },
            }
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


def test_calendar_days_are_sorted_and_private_count_is_read() -> None:
    days, private = parse_calendar(calendar_payload())
    assert [d.date.isoformat() for d in days] == [
        "2026-11-01",
        "2026-11-02",
        "2026-11-03",
    ]
    assert [d.count for d in days] == [0, 3, 5]
    assert private == 7


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

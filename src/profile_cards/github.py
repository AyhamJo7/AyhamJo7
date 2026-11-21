"""Fetch a profile snapshot from the GitHub GraphQL and REST APIs."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import date, timedelta
from typing import Any

from profile_cards.config import Config, ProjectConfig
from profile_cards.model import (
    COMMIT_WEEKS,
    YEAR_DAYS,
    Day,
    Project,
    Snapshot,
    Upstream,
    UpstreamPull,
    UpstreamRepo,
)
from profile_cards.stats import streaks

log = logging.getLogger(__name__)

API_ROOT = "https://api.github.com"
GRAPHQL_URL = f"{API_ROOT}/graphql"
USER_AGENT = "profile-cards"
REQUEST_TIMEOUT_SECONDS = 30
CALENDAR_WINDOW_DAYS = YEAR_DAYS - 1
# The two latest years are always fetched (the cards show both); older years only
# while the current streak still runs back to the oldest day, up to a limit.
HISTORY_WINDOWS_MIN = 2
HISTORY_WINDOWS_MAX = 6
SEARCH_PAGE_SIZE = 100
STATS_ATTEMPTS = 8
STATS_RETRY_SECONDS = 4
HTTP_ACCEPTED = 202

YEAR_FRAGMENT = """
fragment Year on ContributionsCollection {
  restrictedContributionsCount
  contributionCalendar {
    weeks { contributionDays { date contributionCount } }
  }
}
"""

# One year of the calendar; GitHub limits a contributionsCollection to a year.
YEAR_QUERY = (
    YEAR_FRAGMENT
    + """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) { ...Year }
  }
}
"""
)

CALENDAR_QUERY = (
    YEAR_FRAGMENT
    + """
query($login: String!, $from: DateTime!, $to: DateTime!,
      $previousFrom: DateTime!, $previousTo: DateTime!,
      $mergedQuery: String!, $openQuery: String!, $page: Int!) {
  user(login: $login) {
    current: contributionsCollection(from: $from, to: $to) { ...Year }
    previous: contributionsCollection(from: $previousFrom, to: $previousTo) { ...Year }
  }
  merged: search(query: $mergedQuery, type: ISSUE, first: $page) {
    nodes { ... on PullRequest {
      title url mergedAt
      repository { nameWithOwner stargazerCount isPrivate }
    } }
  }
  open: search(query: $openQuery, type: ISSUE, first: 1) { issueCount }
}
"""
)


class GitHubError(RuntimeError):
    """GitHub could not be reached or returned an unusable answer."""


def _call(
    url: str, token: str, body: dict[str, Any] | None = None
) -> tuple[int, dict[str, Any] | list[Any]]:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as reply:
            raw = reply.read()
            payload = json.loads(raw) if raw else {}
            return reply.status, payload
    except urllib.error.HTTPError as error:
        raise GitHubError(f"GitHub answered HTTP {error.code} for {url}") from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise GitHubError(f"GitHub request failed for {url}: {error!r}") from error


def _graphql(query: str, variables: dict[str, Any], token: str) -> dict[str, Any]:
    _, payload = _call(GRAPHQL_URL, token, {"query": query, "variables": variables})
    if not isinstance(payload, dict) or payload.get("errors"):
        errors = payload.get("errors") if isinstance(payload, dict) else payload
        raise GitHubError(f"GraphQL query failed: {errors!r}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise GitHubError("GraphQL answer carries no data")
    return data


def _parse_year(collection: dict[str, Any]) -> tuple[dict[date, int], int]:
    days = {
        date.fromisoformat(item["date"]): int(item["contributionCount"])
        for week in collection["contributionCalendar"]["weeks"]
        for item in week["contributionDays"]
    }
    return days, int(collection["restrictedContributionsCount"])


def parse_calendar(data: dict[str, Any]) -> tuple[tuple[Day, ...], int, int]:
    """Days of the two latest 12-month windows plus each window's private count."""
    current, private = _parse_year(data["user"]["current"])
    previous, private_previous = _parse_year(data["user"]["previous"])
    merged = {**previous, **current}
    return tuple(Day(d, merged[d]) for d in sorted(merged)), private, private_previous


def streak_reaches_history_start(days: tuple[Day, ...], today: date) -> bool:
    """True while the current streak runs back to the oldest day fetched.

    Only then can an older year still extend it, so only then is one fetched.
    """
    if not days:
        return False
    return streaks(days, today).current >= len(days) - 1


def parse_upstream(data: dict[str, Any]) -> Upstream:
    """Merged and open pull requests, counting public repositories only."""
    merged: Counter[str] = Counter()
    stars: dict[str, int] = {}
    pulls: list[UpstreamPull] = []
    for node in data["merged"]["nodes"]:
        repository = node.get("repository")
        if repository is None or repository["isPrivate"]:
            continue
        name = repository["nameWithOwner"]
        merged[name] += 1
        stars[name] = int(repository["stargazerCount"])
        pulls.append(
            UpstreamPull(
                repo=name,
                title=str(node["title"]),
                url=str(node["url"]),
                merged=date.fromisoformat(str(node["mergedAt"])[:10]),
            )
        )
    repos = tuple(
        UpstreamRepo(name, stars[name], count)
        for name, count in sorted(merged.items(), key=lambda kv: -stars[kv[0]])
    )
    return Upstream(
        sum(merged.values()),
        int(data["open"]["issueCount"]),
        repos,
        tuple(sorted(pulls, key=lambda pull: pull.merged, reverse=True)),
    )


def parse_commit_activity(payload: Any) -> tuple[int, ...]:
    """The last COMMIT_WEEKS weekly commit totals, oldest first."""
    if not isinstance(payload, list) or not payload:
        raise GitHubError("commit activity is not available yet")
    totals = [int(week["total"]) for week in payload][-COMMIT_WEEKS:]
    return tuple([0] * (COMMIT_WEEKS - len(totals)) + totals)


_PROJECT_QUERY = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    description
    stargazerCount
    isPrivate
    primaryLanguage { name }
  }
}
"""


def _fetch_commit_activity(repo: str, token: str) -> tuple[int, ...]:
    url = f"{API_ROOT}/repos/{repo}/stats/commit_activity"
    for attempt in range(1, STATS_ATTEMPTS + 1):
        status, payload = _call(url, token)
        if status != HTTP_ACCEPTED and payload:
            return parse_commit_activity(payload)
        log.info("commit activity still computing", extra={"repo": repo, "n": attempt})
        time.sleep(STATS_RETRY_SECONDS)
    raise GitHubError(f"commit activity for {repo} was not ready in time")


def _fetch_project(entry: ProjectConfig, token: str) -> Project:
    owner, name = entry.repo.split("/")
    data = _graphql(_PROJECT_QUERY, {"owner": owner, "name": name}, token)
    repository = data["repository"]
    if repository is None or repository["isPrivate"]:
        raise GitHubError(f"{entry.repo} is not a public repository")
    language = repository["primaryLanguage"]
    return Project(
        repo=entry.repo,
        name=name,
        blurb=entry.blurb or repository["description"] or "",
        language=None if language is None else language["name"],
        stars=int(repository["stargazerCount"]),
        weekly_commits=_fetch_commit_activity(entry.repo, token),
    )


def fetch_snapshot(config: Config, token: str, today: date) -> Snapshot:
    """Query GitHub for everything the cards show."""
    login = config.login
    start, end = _window_bounds(today, 0)
    previous_start, previous_end = _window_bounds(today, 1)
    data = _graphql(
        CALENDAR_QUERY,
        {
            "login": login,
            "from": start,
            "to": end,
            "previousFrom": previous_start,
            "previousTo": previous_end,
            "mergedQuery": f"author:{login} is:pr is:merged is:public -user:{login}",
            "openQuery": f"author:{login} is:pr is:open is:public -user:{login}",
            "page": SEARCH_PAGE_SIZE,
        },
        token,
    )
    days, private, private_previous = parse_calendar(data)
    days = _extend_streak_history(login, token, today, days)
    return Snapshot(
        login=login,
        generated=today,
        days=days,
        private_contributions=private,
        private_contributions_previous=private_previous,
        upstream=parse_upstream(data),
        projects=tuple(_fetch_project(entry, token) for entry in config.projects),
    )


def _window_bounds(today: date, index: int) -> tuple[str, str]:
    """ISO timestamps bounding the 365-day window `index`, as GraphQL wants them."""
    end = today - timedelta(days=YEAR_DAYS * index)
    start = end - timedelta(days=CALENDAR_WINDOW_DAYS)
    return f"{start.isoformat()}T00:00:00Z", f"{end.isoformat()}T23:59:59Z"


def _extend_streak_history(
    login: str, token: str, today: date, days: tuple[Day, ...]
) -> tuple[Day, ...]:
    """Fetch older years while the current streak still reaches the oldest day."""
    fetched = HISTORY_WINDOWS_MIN
    while fetched < HISTORY_WINDOWS_MAX and streak_reaches_history_start(days, today):
        start, end = _window_bounds(today, fetched)
        data = _graphql(
            YEAR_QUERY,
            {"login": login, "from": start, "to": end},
            token,
        )
        older, _ = _parse_year(data["user"]["contributionsCollection"])
        merged = {**older, **{day.date: day.count for day in days}}
        days = tuple(Day(d, merged[d]) for d in sorted(merged))
        fetched += 1
    return days

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
    Day,
    Project,
    Snapshot,
    Upstream,
    UpstreamRepo,
)

log = logging.getLogger(__name__)

API_ROOT = "https://api.github.com"
GRAPHQL_URL = f"{API_ROOT}/graphql"
USER_AGENT = "profile-cards"
REQUEST_TIMEOUT_SECONDS = 30
CALENDAR_WINDOW_DAYS = 364
SEARCH_PAGE_SIZE = 100
STATS_ATTEMPTS = 8
STATS_RETRY_SECONDS = 4
HTTP_ACCEPTED = 202

CALENDAR_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!,
      $mergedQuery: String!, $openQuery: String!, $page: Int!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      restrictedContributionsCount
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
  merged: search(query: $mergedQuery, type: ISSUE, first: $page) {
    nodes { ... on PullRequest {
      repository { nameWithOwner stargazerCount isPrivate }
    } }
  }
  open: search(query: $openQuery, type: ISSUE, first: 1) { issueCount }
}
"""


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


def parse_calendar(data: dict[str, Any]) -> tuple[tuple[Day, ...], int]:
    """Days of the contribution calendar plus the private-contribution count."""
    collection = data["user"]["contributionsCollection"]
    days = {
        date.fromisoformat(item["date"]): int(item["contributionCount"])
        for week in collection["contributionCalendar"]["weeks"]
        for item in week["contributionDays"]
    }
    ordered = tuple(Day(d, days[d]) for d in sorted(days))
    return ordered, int(collection["restrictedContributionsCount"])


def parse_upstream(data: dict[str, Any]) -> Upstream:
    """Merged and open pull requests, counting public repositories only."""
    merged: Counter[str] = Counter()
    stars: dict[str, int] = {}
    for node in data["merged"]["nodes"]:
        repository = node.get("repository")
        if repository is None or repository["isPrivate"]:
            continue
        name = repository["nameWithOwner"]
        merged[name] += 1
        stars[name] = int(repository["stargazerCount"])
    repos = tuple(
        UpstreamRepo(name, stars[name], count)
        for name, count in sorted(merged.items(), key=lambda kv: -stars[kv[0]])
    )
    return Upstream(sum(merged.values()), int(data["open"]["issueCount"]), repos)


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
    window_start = today - timedelta(days=CALENDAR_WINDOW_DAYS)
    data = _graphql(
        CALENDAR_QUERY,
        {
            "login": login,
            "from": f"{window_start.isoformat()}T00:00:00Z",
            "to": f"{today.isoformat()}T23:59:59Z",
            "mergedQuery": f"author:{login} is:pr is:merged is:public -user:{login}",
            "openQuery": f"author:{login} is:pr is:open is:public -user:{login}",
            "page": SEARCH_PAGE_SIZE,
        },
        token,
    )
    days, private = parse_calendar(data)
    return Snapshot(
        login=login,
        generated=today,
        days=days,
        private_contributions=private,
        upstream=parse_upstream(data),
        projects=tuple(_fetch_project(entry, token) for entry in config.projects),
    )

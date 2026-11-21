"""Data model of one profile snapshot and its JSON form."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

SCHEMA_VERSION = 1
COMMIT_WEEKS = 12


@dataclass(frozen=True)
class Day:
    date: date
    count: int


@dataclass(frozen=True)
class UpstreamRepo:
    name: str
    stars: int
    merged: int


@dataclass(frozen=True)
class Upstream:
    """Pull requests sent to public repositories the user does not own."""

    merged_prs: int
    open_prs: int
    repos: tuple[UpstreamRepo, ...]

    @property
    def reach(self) -> int:
        return sum(repo.stars for repo in self.repos)


@dataclass(frozen=True)
class Project:
    repo: str
    name: str
    blurb: str
    language: str | None
    stars: int
    weekly_commits: tuple[int, ...]

    @property
    def commits(self) -> int:
        return sum(self.weekly_commits)


@dataclass(frozen=True)
class Snapshot:
    login: str
    generated: date
    days: tuple[Day, ...]
    private_contributions: int
    upstream: Upstream
    projects: tuple[Project, ...]

    @property
    def total(self) -> int:
        return sum(day.count for day in self.days)


def snapshot_to_json(snapshot: Snapshot) -> str:
    payload: dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "login": snapshot.login,
        "generated": snapshot.generated.isoformat(),
        "private_contributions": snapshot.private_contributions,
        "days": [[day.date.isoformat(), day.count] for day in snapshot.days],
        "upstream": {
            "merged_prs": snapshot.upstream.merged_prs,
            "open_prs": snapshot.upstream.open_prs,
            "repos": [
                {"name": r.name, "stars": r.stars, "merged": r.merged}
                for r in snapshot.upstream.repos
            ],
        },
        "projects": [
            {
                "repo": p.repo,
                "name": p.name,
                "blurb": p.blurb,
                "language": p.language,
                "stars": p.stars,
                "weekly_commits": list(p.weekly_commits),
            }
            for p in snapshot.projects
        ],
    }
    return json.dumps(payload, indent=1, ensure_ascii=False) + "\n"


def snapshot_from_json(text: str) -> Snapshot:
    """Parse a snapshot; raises ValueError when the document is not one."""
    try:
        raw = json.loads(text)
        if raw["schema"] != SCHEMA_VERSION:
            raise ValueError(f"unsupported snapshot schema {raw['schema']!r}")
        return Snapshot(
            login=str(raw["login"]),
            generated=date.fromisoformat(raw["generated"]),
            days=tuple(Day(date.fromisoformat(d), int(c)) for d, c in raw["days"]),
            private_contributions=int(raw["private_contributions"]),
            upstream=Upstream(
                merged_prs=int(raw["upstream"]["merged_prs"]),
                open_prs=int(raw["upstream"]["open_prs"]),
                repos=tuple(
                    UpstreamRepo(str(r["name"]), int(r["stars"]), int(r["merged"]))
                    for r in raw["upstream"]["repos"]
                ),
            ),
            projects=tuple(
                Project(
                    repo=str(p["repo"]),
                    name=str(p["name"]),
                    blurb=str(p["blurb"]),
                    language=None if p["language"] is None else str(p["language"]),
                    stars=int(p["stars"]),
                    weekly_commits=tuple(int(w) for w in p["weekly_commits"]),
                )
                for p in raw["projects"]
            ),
        )
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid snapshot document: {error!r}") from error

"""Shared fixtures: a deterministic snapshot and the repository configuration."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from profile_cards.config import Config, load_config
from profile_cards.model import (
    COMMIT_WEEKS,
    Day,
    Project,
    Snapshot,
    Upstream,
    UpstreamRepo,
)

TODAY = date(2026, 11, 21)
WINDOW_DAYS = 365
REPO_ROOT = Path(__file__).resolve().parent.parent


def make_days(today: date = TODAY, length: int = WINDOW_DAYS) -> tuple[Day, ...]:
    """A year of days with a repeating pattern that includes zero-count days."""
    start = today - timedelta(days=length - 1)
    return tuple(Day(start + timedelta(days=i), (i * 7) % 13) for i in range(length))


@pytest.fixture
def config() -> Config:
    return load_config(REPO_ROOT / "config.toml")


@pytest.fixture
def snapshot() -> Snapshot:
    return Snapshot(
        login="AyhamJo7",
        generated=TODAY,
        days=make_days(),
        private_contributions=120,
        upstream=Upstream(
            merged_prs=3,
            open_prs=2,
            repos=(
                UpstreamRepo("big/project", 5000, 2),
                UpstreamRepo("small/tool", 40, 1),
            ),
        ),
        projects=tuple(
            Project(
                repo=f"AyhamJo7/p{i}",
                name=f"p{i}",
                blurb='A <b>bold</b> & "quoted" blurb that stays inert',
                language="Python",
                stars=i,
                weekly_commits=tuple(range(COMMIT_WEEKS)),
            )
            for i in range(1, 4)
        ),
    )

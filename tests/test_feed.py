from __future__ import annotations

import json
from datetime import timedelta

from profile_cards.config import Config
from profile_cards.feed import FEED_SCHEMA, site_feed
from profile_cards.model import YEAR_DAYS, Snapshot
from profile_cards.render import render_all


def test_feed_holds_the_latest_year_day_by_day(snapshot: Snapshot) -> None:
    feed = json.loads(site_feed(snapshot))
    assert feed["schema"] == FEED_SCHEMA
    assert feed["generated"] == snapshot.generated.isoformat()
    days = feed["year"]["days"]
    assert len(days) == YEAR_DAYS
    assert days[-1][0] == snapshot.generated.isoformat()
    assert feed["year"]["total"] == snapshot.total == sum(count for _, count in days)


def test_feed_rhythm_counts_active_days_in_the_last_two_years(
    snapshot: Snapshot,
) -> None:
    feed = json.loads(site_feed(snapshot))
    start = snapshot.generated - timedelta(days=YEAR_DAYS * 2 - 1)
    window = [d for d in snapshot.days if start <= d.date <= snapshot.generated]
    assert feed["rhythm"] == {
        "active_days": sum(1 for d in window if d.count > 0),
        "span_days": len(window),
    }


def test_feed_lists_merged_pulls_and_nothing_private(snapshot: Snapshot) -> None:
    feed = json.loads(site_feed(snapshot))
    assert [p["repo"] for p in feed["merged"]] == ["big/project", "small/tool"]
    assert set(feed) == {"schema", "login", "generated", "year", "rhythm", "merged"}
    assert "private_contributions" not in site_feed(snapshot)


def test_render_all_publishes_the_feed(config: Config, snapshot: Snapshot) -> None:
    files = render_all(config, snapshot)
    assert json.loads(files["cards/site.json"])["login"] == snapshot.login

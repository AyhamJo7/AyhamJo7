"""The site feed: the public numbers iquantum.co renders in its own design.

Written next to the cards as `cards/site.json`. It carries only what the
profile already shows publicly: daily contribution counts for the latest
year, how many of the last two years' days had a contribution, and merged
pull requests in public repositories the user does not own.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from profile_cards.model import YEAR_DAYS, Snapshot

FEED_SCHEMA = 1
RHYTHM_YEARS = 2


def site_feed(snapshot: Snapshot) -> str:
    rhythm_start = snapshot.generated - timedelta(days=YEAR_DAYS * RHYTHM_YEARS - 1)
    rhythm = [
        day for day in snapshot.days if rhythm_start <= day.date <= snapshot.generated
    ]
    payload: dict[str, Any] = {
        "schema": FEED_SCHEMA,
        "login": snapshot.login,
        "generated": snapshot.generated.isoformat(),
        "year": {
            "total": snapshot.total,
            "days": [[day.date.isoformat(), day.count] for day in snapshot.window(0)],
        },
        "rhythm": {
            "active_days": sum(1 for day in rhythm if day.count > 0),
            "span_days": len(rhythm),
        },
        "merged": [
            {
                "repo": pull.repo,
                "title": pull.title,
                "url": pull.url,
                "merged": pull.merged.isoformat(),
            }
            for pull in snapshot.upstream.pulls
        ],
    }
    return json.dumps(payload, indent=1, ensure_ascii=False) + "\n"

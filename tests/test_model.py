from __future__ import annotations

import json
from dataclasses import replace
from datetime import timedelta

import pytest

from profile_cards.model import (
    YEAR_DAYS,
    Snapshot,
    snapshot_from_json,
    snapshot_to_json,
)


def test_snapshot_survives_a_json_round_trip(snapshot: Snapshot) -> None:
    assert snapshot_from_json(snapshot_to_json(snapshot)) == snapshot


def test_snapshot_total_is_the_latest_twelve_months_only(snapshot: Snapshot) -> None:
    latest = sum(day.count for day in snapshot.window(0))
    assert snapshot.total == latest
    assert snapshot.total < sum(day.count for day in snapshot.days)


def test_windows_are_consecutive_year_long_and_do_not_overlap(
    snapshot: Snapshot,
) -> None:
    latest, previous = snapshot.window(0), snapshot.window(1)
    assert len(latest) == len(previous) == YEAR_DAYS
    assert latest[-1].date == snapshot.generated
    assert previous[-1].date == latest[0].date - timedelta(days=1)
    assert not {d.date for d in latest} & {d.date for d in previous}
    assert snapshot.window_end(1) == previous[-1].date


def test_a_previous_year_exists_only_when_a_full_year_was_fetched(
    snapshot: Snapshot,
) -> None:
    assert snapshot.has_previous_year
    one_year = replace(snapshot, days=snapshot.window(0))
    assert not one_year.has_previous_year
    partial = replace(snapshot, days=snapshot.window(0) + snapshot.window(1)[-100:])
    assert not partial.has_previous_year


def test_the_previous_private_count_survives_json_and_defaults_to_zero(
    snapshot: Snapshot,
) -> None:
    restored = snapshot_from_json(snapshot_to_json(snapshot))
    assert restored.private_contributions_previous == 300
    document = json.loads(snapshot_to_json(snapshot))
    del document["private_contributions_previous"]
    legacy = snapshot_from_json(json.dumps(document))
    assert legacy.private_contributions_previous == 0


def test_snapshot_with_an_unknown_schema_is_rejected(snapshot: Snapshot) -> None:
    document = json.loads(snapshot_to_json(snapshot))
    document["schema"] = 99
    with pytest.raises(ValueError, match="schema"):
        snapshot_from_json(json.dumps(document))


@pytest.mark.parametrize("text", ["", "not json", "{}", '{"schema": 1}', "[]"])
def test_garbage_is_rejected_with_value_error(text: str) -> None:
    with pytest.raises(ValueError, match="invalid snapshot"):
        snapshot_from_json(text)

from __future__ import annotations

import json

import pytest

from profile_cards.model import Snapshot, snapshot_from_json, snapshot_to_json


def test_snapshot_survives_a_json_round_trip(snapshot: Snapshot) -> None:
    assert snapshot_from_json(snapshot_to_json(snapshot)) == snapshot


def test_snapshot_total_sums_the_days(snapshot: Snapshot) -> None:
    assert snapshot.total == sum(day.count for day in snapshot.days)


def test_snapshot_with_an_unknown_schema_is_rejected(snapshot: Snapshot) -> None:
    document = json.loads(snapshot_to_json(snapshot))
    document["schema"] = 99
    with pytest.raises(ValueError, match="schema"):
        snapshot_from_json(json.dumps(document))


@pytest.mark.parametrize("text", ["", "not json", "{}", '{"schema": 1}', "[]"])
def test_garbage_is_rejected_with_value_error(text: str) -> None:
    with pytest.raises(ValueError, match="invalid snapshot"):
        snapshot_from_json(text)

from __future__ import annotations

from pathlib import Path

import pytest

from profile_cards.cli import EXIT_FAILURE, TOKEN_ENV, main
from profile_cards.model import Snapshot, snapshot_to_json
from tests.conftest import REPO_ROOT


def test_render_writes_every_card_from_a_snapshot(
    snapshot: Snapshot, tmp_path: Path
) -> None:
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(snapshot_to_json(snapshot), encoding="utf-8")
    code = main(
        [
            "render",
            "--config",
            str(REPO_ROOT / "config.toml"),
            "--snapshot",
            str(snapshot_path),
            "--root",
            str(tmp_path),
        ]
    )
    assert code == 0
    assert (tmp_path / "README.md").read_text(encoding="utf-8").startswith("<!--")
    assert len(list((tmp_path / "cards").glob("*.svg"))) == 10


def test_render_fails_cleanly_on_a_missing_snapshot(tmp_path: Path) -> None:
    code = main(
        [
            "render",
            "--config",
            str(REPO_ROOT / "config.toml"),
            "--snapshot",
            str(tmp_path / "missing.json"),
            "--root",
            str(tmp_path),
        ]
    )
    assert code == EXIT_FAILURE


def test_fetch_without_a_token_fails_before_any_network_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(TOKEN_ENV, raising=False)
    code = main(
        [
            "fetch",
            "--config",
            str(REPO_ROOT / "config.toml"),
            "--snapshot",
            str(tmp_path / "snapshot.json"),
        ]
    )
    assert code == EXIT_FAILURE
    assert not (tmp_path / "snapshot.json").exists()

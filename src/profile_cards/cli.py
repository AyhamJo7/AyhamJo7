"""Command line entry point: fetch, render, or both."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from profile_cards.config import ConfigError, load_config
from profile_cards.github import GitHubError, fetch_snapshot
from profile_cards.model import Snapshot, snapshot_from_json, snapshot_to_json
from profile_cards.render import render_all

log = logging.getLogger("profile_cards")

TOKEN_ENV = "GITHUB_TOKEN"
EXIT_FAILURE = 1
_STANDARD_RECORD_FIELDS = frozenset(logging.makeLogRecord({}).__dict__) | {"message"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="profile-cards", description=__doc__)
    parser.add_argument("command", choices=("fetch", "render", "refresh"))
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    parser.add_argument("--snapshot", type=Path, default=Path("snapshot.json"))
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="output root")
    return parser


def _fetch(config_path: Path, snapshot_path: Path) -> Snapshot:
    token = os.environ.get(TOKEN_ENV)
    if not token:
        raise GitHubError(
            f"set {TOKEN_ENV} (for example GITHUB_TOKEN=$(gh auth token))"
        )
    snapshot = fetch_snapshot(load_config(config_path), token, datetime.now(UTC).date())
    snapshot_path.write_text(snapshot_to_json(snapshot), encoding="utf-8")
    log.info("snapshot written", extra={"path": str(snapshot_path)})
    return snapshot


def _render(config_path: Path, snapshot: Snapshot, root: Path) -> None:
    for relative, content in render_all(load_config(config_path), snapshot).items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        log.info("file written", extra={"path": relative, "bytes": len(content)})


class _JsonFormatter(logging.Formatter):
    """One JSON object per record, carrying the `extra` fields as keys."""

    def format(self, record: logging.LogRecord) -> str:
        fields = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_RECORD_FIELDS
        }
        return json.dumps(
            {"level": record.levelname, "event": record.getMessage(), **fields},
            default=str,
        )


def _configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


def main(argv: Sequence[str] | None = None) -> int:
    _configure_logging()
    args = _parser().parse_args(argv)
    try:
        if args.command == "render":
            snapshot = snapshot_from_json(args.snapshot.read_text(encoding="utf-8"))
        else:
            snapshot = _fetch(args.config, args.snapshot)
        if args.command != "fetch":
            _render(args.config, snapshot, args.root)
    except (ConfigError, GitHubError, ValueError, OSError) as error:
        log.error("failed", extra={"error": repr(error)})
        return EXIT_FAILURE
    return 0


if __name__ == "__main__":
    sys.exit(main())

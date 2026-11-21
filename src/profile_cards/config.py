"""Profile configuration, validated at load time."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

MAX_PROJECTS = 3
MAX_TAGLINE_CHARS = 160
MAX_BLURB_CHARS = 200
LOGIN_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
REPO_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}$")


class ConfigError(ValueError):
    """The configuration file is missing a field or holds an invalid value."""


@dataclass(frozen=True)
class ProjectConfig:
    repo: str
    blurb: str | None


@dataclass(frozen=True)
class Link:
    label: str
    url: str


@dataclass(frozen=True)
class Config:
    login: str
    name: str
    role: str
    location: str
    tagline: str
    site_url: str
    site_label: str
    projects: tuple[ProjectConfig, ...]
    links: tuple[Link, ...]

    @property
    def first_name(self) -> str:
        return self.name.rsplit(" ", 1)[0]

    @property
    def last_name(self) -> str:
        return self.name.rsplit(" ", 1)[-1]


def _text(table: dict[str, object], key: str, limit: int) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{key} must be a non-empty string")
    if len(value) > limit:
        raise ConfigError(f"{key} is longer than {limit} characters")
    return value.strip()


def _https_url(value: object, key: str) -> str:
    parsed = urlparse(value) if isinstance(value, str) else None
    if parsed is None or parsed.scheme != "https" or not parsed.netloc:
        raise ConfigError(f"{key} must be an https URL")
    return str(value)


def parse_config(raw: dict[str, object]) -> Config:
    login = _text(raw, "login", 39)
    if not LOGIN_PATTERN.match(login):
        raise ConfigError("login is not a valid GitHub username")
    name = _text(raw, "name", 60)
    if " " not in name:
        raise ConfigError("name must contain a first and a last name")

    projects: list[ProjectConfig] = []
    for entry in _tables(raw, "projects"):
        repo = _text(entry, "repo", 140)
        if not REPO_PATTERN.match(repo):
            raise ConfigError(f"projects.repo {repo!r} must look like owner/name")
        blurb = entry.get("blurb")
        if blurb is not None:
            blurb = _text(entry, "blurb", MAX_BLURB_CHARS)
        projects.append(ProjectConfig(repo, blurb))
    if not 1 <= len(projects) <= MAX_PROJECTS:
        raise ConfigError(f"configure between 1 and {MAX_PROJECTS} projects")

    links = tuple(
        Link(_text(entry, "label", 30), _https_url(entry.get("url"), "links.url"))
        for entry in _tables(raw, "links")
    )
    return Config(
        login=login,
        name=name,
        role=_text(raw, "role", 40),
        location=_text(raw, "location", 40),
        tagline=_text(raw, "tagline", MAX_TAGLINE_CHARS),
        site_url=_https_url(raw.get("site_url"), "site_url"),
        site_label=_text(raw, "site_label", 40),
        projects=tuple(projects),
        links=links,
    )


def _tables(raw: dict[str, object], key: str) -> list[dict[str, object]]:
    value = raw.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
        raise ConfigError(f"{key} must be an array of tables")
    return value


def load_config(path: Path) -> Config:
    with path.open("rb") as handle:
        return parse_config(tomllib.load(handle))

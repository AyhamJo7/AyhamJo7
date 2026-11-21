from __future__ import annotations

from typing import Any

import pytest

from profile_cards.config import Config, ConfigError, parse_config


def valid() -> dict[str, Any]:
    return {
        "login": "AyhamJo7",
        "name": "Ayham Joumran",
        "role": "AI Engineer",
        "location": "Hamburg",
        "tagline": "One sentence.",
        "site_url": "https://example.com",
        "site_label": "example.com",
        "projects": [{"repo": "AyhamJo7/moin", "blurb": "A blurb."}],
        "links": [{"label": "site", "url": "https://example.com"}],
    }


def test_repository_config_is_valid(config: Config) -> None:
    assert config.login == "AyhamJo7"
    assert config.first_name == "Ayham"
    assert config.last_name == "Joumran"
    assert 1 <= len(config.projects) <= 3


def test_blurb_is_optional() -> None:
    raw = valid()
    raw["projects"] = [{"repo": "AyhamJo7/moin"}]
    assert parse_config(raw).projects[0].blurb is None


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("site_url", "http://example.com"),
        ("site_url", "javascript:alert(1)"),
        ("site_url", "https://"),
        ("login", "bad login"),
        ("login", "-leading-dash"),
        ("name", "Mononym"),
        ("role", ""),
        ("tagline", "x" * 161),
    ],
)
def test_invalid_scalar_values_are_rejected(key: str, value: str) -> None:
    raw = valid()
    raw[key] = value
    with pytest.raises(ConfigError):
        parse_config(raw)


@pytest.mark.parametrize(
    "repo", ["no-slash", "a/b/c", "owner/", "ow ner/name", "../x/y"]
)
def test_invalid_repository_names_are_rejected(repo: str) -> None:
    raw = valid()
    raw["projects"] = [{"repo": repo}]
    with pytest.raises(ConfigError):
        parse_config(raw)


def test_project_count_is_bounded() -> None:
    raw = valid()
    raw["projects"] = []
    with pytest.raises(ConfigError):
        parse_config(raw)
    raw["projects"] = [{"repo": f"o/r{i}"} for i in range(4)]
    with pytest.raises(ConfigError):
        parse_config(raw)


def test_link_urls_must_be_https() -> None:
    raw = valid()
    raw["links"] = [{"label": "x", "url": "ftp://example.com"}]
    with pytest.raises(ConfigError):
        parse_config(raw)

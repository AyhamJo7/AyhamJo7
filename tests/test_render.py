from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import replace

import pytest

from profile_cards.config import Config
from profile_cards.model import Snapshot
from profile_cards.render import render_all
from profile_cards.theme import compact, esc, fmt_int, shade, wrap

EXPECTED_FILES = {
    "README.md",
    "cards/hero.svg",
    "cards/heatmap.svg",
    "cards/activity.svg",
    "cards/upstream.svg",
    "cards/coding.svg",
    "cards/project-1.svg",
    "cards/project-2.svg",
    "cards/project-3.svg",
}
SVG_NS = "{http://www.w3.org/2000/svg}"


@pytest.fixture
def files(config: Config, snapshot: Snapshot) -> dict[str, str]:
    return render_all(config, snapshot)


def test_every_expected_file_is_rendered(files: dict[str, str]) -> None:
    assert set(files) == EXPECTED_FILES


def test_every_card_is_well_formed_xml_with_an_accessible_name(
    files: dict[str, str],
) -> None:
    for path, content in files.items():
        if not path.endswith(".svg"):
            continue
        root = ET.fromstring(content)
        assert root.tag == f"{SVG_NS}svg", path
        assert root.get("role") == "img", path
        assert root.find(f"{SVG_NS}title") is not None, path
        assert root.find(f"{SVG_NS}desc") is not None, path


def test_cards_contain_no_scripts_or_external_references(files: dict[str, str]) -> None:
    for path, content in files.items():
        if not path.endswith(".svg"):
            continue
        assert "<script" not in content, path
        assert "javascript:" not in content, path
        assert "onload" not in content, path
        assert not re.search(r'(?:href|src)="https?://', content), path
        assert not re.search(r"url\(\s*['\"]?https?://", content), path


def test_cards_support_dark_mode_and_reduced_motion(files: dict[str, str]) -> None:
    for path, content in files.items():
        if path.endswith(".svg"):
            assert "prefers-color-scheme:dark" in content, path
            assert "prefers-reduced-motion:reduce" in content, path


def test_untrusted_text_cannot_inject_markup(
    config: Config, snapshot: Snapshot
) -> None:
    hostile = '</text><script>alert(1)</script><text x="">'
    project = replace(snapshot.projects[0], blurb=hostile, name='"><svg onload=x>')
    files = render_all(config, replace(snapshot, projects=(project,)))
    card = files["cards/project-1.svg"]
    ET.fromstring(card)
    assert "<script" not in card
    assert "<svg onload" not in card
    assert "&lt;script&gt;" in card


def test_hero_draws_the_portrait_as_ink_seen_through_an_embedded_mask(
    files: dict[str, str],
) -> None:
    root = ET.fromstring(files["cards/hero.svg"])
    assert root.find(f".//{SVG_NS}mask[@id='portrait']") is not None
    image = root.find(f".//{SVG_NS}mask[@id='portrait']/{SVG_NS}image")
    assert image is not None
    assert (image.get("href") or "").startswith("data:image/webp;base64,")
    sketch = root.find(f".//{SVG_NS}rect[@mask='url(#portrait)']")
    assert sketch is not None
    assert "sketch" in (sketch.get("class") or "").split()
    assert root.find(f".//{SVG_NS}mask[@id='figure']") is not None
    panel = [
        r
        for r in root.iter(f"{SVG_NS}rect")
        if "panel" in (r.get("class") or "").split()
    ]
    assert len(panel) == 1, "dark mode lights the figure with a paper panel"
    assert panel[0].get("mask") == "url(#figure)", "the panel is cut to the outline"
    for attribute in ("x", "y", "width", "height"):
        assert panel[0].get(attribute) == sketch.get(attribute)


def test_hero_light_is_one_natively_animated_gradient_per_surface(
    files: dict[str, str],
) -> None:
    """The light must be a gradient animated with SMIL, not a mask child.

    Animating an element inside a <mask> does not repaint in Chrome, which left the
    light frozen off-screen in the live profile.
    """
    root = ET.fromstring(files["cards/hero.svg"])
    assert root.find(f".//{SVG_NS}mask[@id='sweep']") is None
    for identifier in ("glowOnInk", "glowOnBlue"):
        gradient = root.find(f".//{SVG_NS}linearGradient[@id='{identifier}']")
        assert gradient is not None
        assert gradient.get("gradientUnits") == "userSpaceOnUse"
        animation = gradient.find(f"{SVG_NS}animateTransform")
        assert animation is not None
        assert animation.get("attributeName") == "gradientTransform"
        assert animation.get("repeatCount") == "indefinite"
        assert animation.get("additive") == "sum"


def test_hero_light_reaches_the_name_and_then_the_portrait(
    files: dict[str, str],
) -> None:
    root = ET.fromstring(files["cards/hero.svg"])
    glows = [
        element
        for element in root.iter()
        if "glow" in (element.get("class") or "").split()
    ]
    fills = [element.get("style") or "" for element in glows]
    assert [text for text in glows if text.tag == f"{SVG_NS}text"]
    assert sum("url(#glowOnInk)" in fill for fill in fills) == 2, "first name + photo"
    assert sum("url(#glowOnBlue)" in fill for fill in fills) == 1, "last name"
    portrait_glow = [g for g in glows if g.get("mask") == "url(#portrait)"]
    assert len(portrait_glow) == 1, "the light continues over the portrait"


def test_hero_light_is_hidden_when_reduced_motion_is_requested(
    files: dict[str, str],
) -> None:
    assert ".glow{display:none}" in files["cards/hero.svg"]


def test_hero_without_a_portrait_still_renders(
    config: Config, snapshot: Snapshot, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("profile_cards.cards.hero.load_portrait", lambda: None)
    hero = render_all(config, snapshot)["cards/hero.svg"]
    root = ET.fromstring(hero)
    assert root.find(f".//{SVG_NS}mask[@id='portrait']") is None


def test_hero_carries_name_role_and_site_label(
    files: dict[str, str], config: Config
) -> None:
    hero = files["cards/hero.svg"]
    for expected in (
        config.first_name,
        config.last_name,
        config.role,
        config.site_label,
    ):
        assert expected in hero


def test_readme_links_to_the_site_and_the_projects(
    files: dict[str, str], config: Config, snapshot: Snapshot
) -> None:
    readme = files["README.md"]
    assert f'<a href="{config.site_url}">' in readme
    for project in snapshot.projects:
        assert f'href="https://github.com/{project.repo}"' in readme
    assert readme.count("<img ") == 8
    assert "\n\n<" not in readme.split("</div>")[0]


def test_readme_images_have_alt_text(files: dict[str, str]) -> None:
    images = re.findall(r"<img [^>]*>", files["README.md"])
    assert images
    assert all('alt="' in image and 'alt=""' not in image for image in images)


def test_a_year_without_activity_still_renders(
    config: Config, snapshot: Snapshot
) -> None:
    quiet = replace(
        snapshot,
        days=tuple(replace(d, count=0) for d in snapshot.days),
        private_contributions=0,
    )
    for path, content in render_all(config, quiet).items():
        if path.endswith(".svg"):
            ET.fromstring(content)


def test_formatting_helpers() -> None:
    assert fmt_int(3586) == "3,586"
    assert [compact(n) for n in (0, 999, 1000, 1234, 766_000, 1_200_000)] == [
        "0",
        "999",
        "1K",
        "1.2K",
        "766K",
        "1.2M",
    ]
    assert esc('<a href="x">&') == "&lt;a href=&quot;x&quot;&gt;&amp;"
    assert shade("#ffffff", 0.5) == "#808080"
    assert all(len(line) <= 20 for line in wrap("word " * 40, 120, 12))

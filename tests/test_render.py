from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import replace

import pytest

from profile_cards.config import Config
from profile_cards.model import YEAR_DAYS, Snapshot
from profile_cards.render import render_all
from profile_cards.stats import MONTH_NAMES
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
    "cards/activity-previous.svg",
    "cards/toggle-previous.svg",
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


def test_cards_support_dark_mode(files: dict[str, str]) -> None:
    for path, content in files.items():
        if path.endswith(".svg"):
            assert "prefers-color-scheme:dark" in content, path


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
    assert "shine-sketch" in (sketch.get("class") or "").split()
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


SHINE_GRADIENTS = [
    f"{surface}{scheme}"
    for surface in ("shineName", "shineSurname", "shineSketch")
    for scheme in ("Light", "Dark")
]


def test_hero_light_is_the_fill_of_each_surface_slid_by_a_plain_animation(
    files: dict[str, str],
) -> None:
    """The light is a gradient fill moved by a plain SMIL animateTransform.

    This mirrors the proven mechanism of the card it was modelled on. Animating an
    element inside a <mask> never repaints in Chrome, and a light kept on separate
    overlay copies can be hidden by a media query; neither is allowed here.
    """
    root = ET.fromstring(files["cards/hero.svg"])
    assert root.find(f".//{SVG_NS}mask[@id='sweep']") is None
    for identifier in SHINE_GRADIENTS:
        gradient = root.find(f".//{SVG_NS}linearGradient[@id='{identifier}']")
        assert gradient is not None, identifier
        assert gradient.get("gradientUnits") == "userSpaceOnUse"
        assert gradient.get("gradientTransform", "").startswith("translate(-"), (
            "the band must rest off the card before it starts"
        )
        stops = gradient.findall(f"{SVG_NS}stop")
        assert all(stop.get("stop-color", "").startswith("#") for stop in stops), (
            "literal colours only, no CSS variables inside stops"
        )
        animation = gradient.find(f"{SVG_NS}animateTransform")
        assert animation is not None
        assert animation.get("attributeName") == "gradientTransform"
        assert animation.get("repeatCount") == "indefinite"
        assert animation.get("additive") is None, "plain replace, no additive sum"
        values = (animation.get("values") or "").split(";")
        key_times = (animation.get("keyTimes") or "").split(";")
        assert len(values) == len(key_times) > 2


def test_hero_light_follows_the_requested_schedule(files: dict[str, str]) -> None:
    """One pass: starts at 1.5 s, ends at 7 s, and the next pass starts at 8 s.

    Event times are seconds after the image loads: the light reaches the name at 1.5,
    has left "Ayham" at 3.8, "Joumran" at about 4.2, reaches the photo at 4.3 and has
    crossed it by 6.5; the band is parked by 7.0 and a new pass starts at 8.0.
    """
    root = ET.fromstring(files["cards/hero.svg"])
    animations = list(root.iter(f"{SVG_NS}animateTransform"))
    assert animations
    for animation in animations:
        begin = float((animation.get("begin") or "").removesuffix("s"))
        duration = float((animation.get("dur") or "").removesuffix("s"))
        key_times = [float(v) for v in (animation.get("keyTimes") or "").split(";")]
        events = [round(begin + k * duration, 2) for k in key_times]
        assert events == [1.5, 3.8, 4.3, 6.5, 7.0, 8.0]
        assert key_times[0] == 0.0
        assert key_times[-1] == 1.0
        assert begin + duration == 8.0, "the next pass starts at 8 s"
        translations = [
            float(v.split()[0]) for v in (animation.get("values") or "").split(";")
        ]
        assert translations == sorted(translations), "the band only moves forward"
        assert translations[-2:] == [translations[-1]] * 2, "parked from 7 s to 8 s"


def test_hero_light_fills_the_name_and_the_portrait_ink(
    files: dict[str, str],
) -> None:
    root = ET.fromstring(files["cards/hero.svg"])

    def classes(element: ET.Element) -> list[str]:
        return (element.get("class") or "").split()

    texts = {t.text: classes(t) for t in root.iter(f"{SVG_NS}text") if t.text}
    assert "shine-name" in texts["Ayham"]
    assert "shine-surname" in texts["Joumran"]
    sketch = [r for r in root.iter(f"{SVG_NS}rect") if "shine-sketch" in classes(r)]
    assert len(sketch) == 1
    assert sketch[0].get("mask") == "url(#portrait)", "the light reaches the photo"
    css = files["cards/hero.svg"]
    for surface in ("shine-name", "shine-surname", "shine-sketch"):
        assert f".{surface}{{fill:url(#" in css


def test_hero_light_does_not_depend_on_reduced_motion(files: dict[str, str]) -> None:
    """The light must play for everyone; nothing may hide or gate it."""
    hero = files["cards/hero.svg"]
    assert "prefers-reduced-motion" not in hero
    assert ".glow" not in hero


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
    assert readme.count("<img ") == 10
    assert "\n\n<" not in readme.split("</div>")[0]


def card_text(svg: str) -> str:
    """All visible text of a card, joined, for simple content assertions."""
    root = ET.fromstring(svg)
    return " ".join("".join(el.itertext()) for el in root.iter(f"{SVG_NS}text"))


def test_the_toggle_is_a_summary_button_that_opens_the_previous_card(
    files: dict[str, str],
) -> None:
    readme = files["README.md"]
    block = readme[readme.index("<details>") : readme.index("</details>")]
    assert "<summary>" in block
    assert "toggle-previous.svg" in block.split("</summary>")[0]
    assert "activity-previous.svg" in block.split("</summary>")[1]
    assert readme.index("activity.svg") < readme.index("<details>")
    assert readme.index("</details>") < readme.index("upstream.svg")
    assert "\n\n" not in block


def test_without_a_full_previous_year_there_is_no_toggle_and_no_extra_card(
    config: Config, snapshot: Snapshot
) -> None:
    one_year = replace(snapshot, days=snapshot.window(0))
    result = render_all(config, one_year)
    assert "cards/activity-previous.svg" not in result
    assert "cards/toggle-previous.svg" not in result
    assert "<details>" not in result["README.md"]
    ET.fromstring(result["cards/activity.svg"])


def test_each_activity_card_shows_the_total_of_its_own_window(
    files: dict[str, str], snapshot: Snapshot
) -> None:
    latest = card_text(files["cards/activity.svg"])
    previous = card_text(files["cards/activity-previous.svg"])
    assert fmt_int(sum(d.count for d in snapshot.window(0))) in latest
    assert fmt_int(sum(d.count for d in snapshot.window(1))) in previous
    assert "The 12 months before" in previous
    assert "The last 12 months" in latest
    assert "300 of them in private" in previous
    assert "120 of them in private" in latest


def test_the_previous_card_dates_its_window_and_its_streak(
    files: dict[str, str], snapshot: Snapshot
) -> None:
    previous = card_text(files["cards/activity-previous.svg"])
    end = snapshot.window_end(1)
    assert f"{end.day} {MONTH_NAMES[end.month - 1]} {end.year}" in previous
    assert f"streak up to {end.day} {MONTH_NAMES[end.month - 1]}" in previous
    assert "current streak" not in previous


def test_the_current_streak_counts_beyond_the_twelve_month_window(
    config: Config, snapshot: Snapshot
) -> None:
    always_active = replace(
        snapshot, days=tuple(replace(d, count=3) for d in snapshot.days)
    )
    latest = card_text(render_all(config, always_active)["cards/activity.svg"])
    assert f"{2 * YEAR_DAYS} days" in latest, "current streak spans both years"
    assert f"{YEAR_DAYS} / {YEAR_DAYS}" in latest, "active days stay per window"


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

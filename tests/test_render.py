from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import replace

import pytest

from profile_cards.cards.activity import _shows_year
from profile_cards.config import Config
from profile_cards.model import YEAR_DAYS, Snapshot
from profile_cards.render import render_all
from profile_cards.stats import MONTH_NAMES, MonthTotal
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
    assert readme.count("<img ") == 8
    assert "The last 24 months on GitHub" in readme
    assert "\n\n<" not in readme.split("</div>")[0]


def card_text(svg: str) -> str:
    """All visible text of a card, joined, for simple content assertions."""
    root = ET.fromstring(svg)
    return " ".join("".join(el.itertext()) for el in root.iter(f"{SVG_NS}text"))


def month_labels(svg: str) -> list[str]:
    """The month names drawn under the bars of the activity card, left to right."""
    root = ET.fromstring(svg)
    return [
        t.text
        for t in root.iter(f"{SVG_NS}text")
        if t.text in MONTH_NAMES and "mono" in (t.get("class") or "")
    ]


def bar_classes(svg: str) -> list[str]:
    """The class of every monthly bar of the activity card (they are the 'grow' rects
    that are taller than the weekday-rhythm bars' base line)."""
    root = ET.fromstring(svg)
    return [
        r.get("class") or ""
        for r in root.iter(f"{SVG_NS}rect")
        if "grow" in (r.get("class") or "").split()
        and float(r.get("width") or 0) < 31
        and float(r.get("x") or 0) < 580
    ]


def test_with_two_years_the_activity_card_shows_24_months_in_one_chart(
    files: dict[str, str], snapshot: Snapshot
) -> None:
    card = files["cards/activity.svg"]
    text = card_text(card)
    assert len(month_labels(card)) == 24
    assert "The last 24 months" in text
    both = sum(d.count for d in snapshot.window(0) + snapshot.window(1))
    assert fmt_int(both) in text, "the headline covers both years"
    assert f"{fmt_int(snapshot.total)} in the last 12 months" in text
    assert f"{fmt_int(both - snapshot.total)} in the 12 months before" in text


def test_the_earlier_year_is_a_lighter_shade_than_the_latest(
    files: dict[str, str],
) -> None:
    classes = bar_classes(files["cards/activity.svg"])
    assert len(classes) == 24
    earlier, latest = classes[:12], classes[12:]
    assert sum("t2" in c for c in earlier) >= 10, "earlier months are the light blue"
    assert sum("t4" in c for c in latest) >= 9, "latest months are the brand blue"
    assert not any("t2" in c for c in latest)


def test_the_card_shows_the_range_both_private_counts_and_year_captions(
    files: dict[str, str], snapshot: Snapshot
) -> None:
    text = card_text(files["cards/activity.svg"])
    start = snapshot.window(1)[0].date
    end = snapshot.generated
    assert f"{start.day} {MONTH_NAMES[start.month - 1]} {start.year}" in text
    assert f"{end.day} {MONTH_NAMES[end.month - 1]} {end.year}" in text
    assert "420 of them in private repositories" in text, "120 + 300 private"
    assert str(end.year) in text
    assert str(end.year - 1) in text


def test_year_captions_never_collide_at_the_first_bar() -> None:
    def series(first_month: int) -> list[MonthTotal]:
        out, year, month = [], 2025, first_month
        for _ in range(24):
            out.append(MonthTotal(year, month, 1, partial=False))
            month += 1
            if month == 13:
                year, month = year + 1, 1
        return out

    december_start = series(12)
    assert [i for i in range(24) if _shows_year(december_start, i)] == [1, 13]
    august_start = series(8)
    assert _shows_year(august_start, 0), "five months before the first January"


def test_the_streak_counts_beyond_the_days_shown_and_active_days_use_both_years(
    config: Config, snapshot: Snapshot
) -> None:
    always_active = replace(
        snapshot, days=tuple(replace(d, count=3) for d in snapshot.days)
    )
    text = card_text(render_all(config, always_active)["cards/activity.svg"])
    assert f"{2 * YEAR_DAYS} days" in text, "current streak spans both years"
    assert f"{2 * YEAR_DAYS} / {2 * YEAR_DAYS}" in text, "active days of 730"


def test_with_one_year_the_card_shows_12_months_and_no_legend(
    config: Config, snapshot: Snapshot
) -> None:
    one_year = replace(snapshot, days=snapshot.window(0))
    result = render_all(config, one_year)
    card = result["cards/activity.svg"]
    text = card_text(card)
    assert len(month_labels(card)) == 12
    assert "The last 12 months" in text
    assert "in the 12 months before" not in text
    assert "The last 12 months on GitHub" in result["README.md"]
    assert "details" not in result["README.md"]


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

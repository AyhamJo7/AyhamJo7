# Developing the profile cards

The profile README is generated. `config.toml` says what the cards claim, `profile-cards`
fetches live data from GitHub and draws eight SVG cards into `cards/` (hero, heatmap,
activity, upstream, a title banner and one card per project), and `README.md` is
rewritten to point at them. A workflow refreshes everything every 6 hours (00:07, 06:07,
12:07 and 18:07 Hamburg winter time, an hour later in summer).

## Commands

```bash
uv sync                                          # install the dev tools
GITHUB_TOKEN=$(gh auth token) uv run profile-cards refresh   # fetch + render
GITHUB_TOKEN=$(gh auth token) uv run profile-cards fetch     # write snapshot.json only
uv run profile-cards render                      # re-render from snapshot.json (offline)
uv run pytest                                    # tests
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

`render` works offline from the last `snapshot.json`, which makes design changes fast.

## Layout

| Path | Role |
| --- | --- |
| `config.toml` | Name, role, sentence, website, the three projects, links |
| `src/profile_cards/github.py` | GraphQL and REST fetching, the only network code |
| `src/profile_cards/stats.py` | Levels, month totals, streaks, grid layout (pure) |
| `src/profile_cards/theme.py` | Palette, light and dark CSS, animations, embedded fonts |
| `src/profile_cards/cards/` | One module per card |
| `src/profile_cards/fonts/` | Subset woff2 fonts, all SIL OFL 1.1 |
| `src/profile_cards/portrait.py`, `assets/` | The portrait masks (ink and figure outline) and their loader |
| `scripts/subset_fonts.py` | Rebuilds the subset fonts from the fontsource packages |
| `scripts/prepare_portrait.py` | Turns a sketch image into the ink mask (Pillow, dev only) |
| `cards/` | Generated SVGs, committed so the profile can display them |

## The token

The refresh workflow needs a repository secret `PROFILE_TOKEN`: a classic personal access
token with the `read:user` scope. The built-in token cannot see private contributions, so
the workflow fails on purpose without the secret instead of publishing lower numbers.

## The activity card: 24 months in one chart

The activity card shows two years at once, with nothing to click.

- **Windows.** `Snapshot.window(0)` is the latest 365 days and `window(1)` the 365 days
  before; `has_previous_year` says whether a complete second window was fetched. With one,
  the card draws 24 monthly bars, the earlier twelve in the lighter blue, a headline for
  both years, and a legend line built from dots in the two bar colours. With only one year
  it falls back to twelve bars and no legend.
- **Streaks use all history, not one window.** The fetcher always reads the two latest
  years, and keeps reading older ones only while the current streak still runs back to the
  oldest day fetched (up to `HISTORY_WINDOWS_MAX`), so a streak is never capped at 365
  days. "Days with a contribution" and the weekday rhythm cover the days the card shows.
- **Why not a button.** A card shown as an image cannot be clicked on GitHub, and an HTML
  `<details>` toggle that opens a second card was tried and judged clumsy, so both years
  share one card instead.

## The portrait

The hero shows a finished sketch of the portrait (dark ink on light paper). To change it,
run

```bash
uv run python scripts/prepare_portrait.py path/to/sketch.png
uv run profile-cards render
```

The script writes two masks (plus the size in `assets/portrait.json`), both feathered at
the sides and bottom:

- `assets/portrait.webp`: the ink. The card fills it with its sketch colour, so in light
  mode the drawing sits directly on the card.
- `assets/figure.webp`: the outline of the person (head, hair, shoulders). In dark mode
  the card fills it with cream "paper" and draws the ink on top, so the face is light and
  the hair dark with no rectangle behind them. In light mode the paper matches the card
  and is invisible.

The outline is found by treating the ink as a wall: gaps up to twice
`FIGURE_GAP_RADIUS` are closed, the background is flooded from the outer edges (not the
bottom, where the open collar would let it run into the face), and what the flood cannot
reach is the figure. Check `figure.webp` by eye after changing the sketch. Paper noise is
cleared with a levels curve (`PAPER_FLOOR`, `INK_CEILING`). Without a prepared portrait
the hero simply renders without one.

## The light in the name

The first name, the last name and the portrait ink are each *filled* with a gradient: the
surface's own colour with one soft slanted band of a brighter colour. The gradient's
transform is moved by a plain SVG `animateTransform` (see `_shine_defs` in
`cards/hero.py`), so one band passes over "Ayham", "Joumran" and then the portrait, left
to right, and rests off the left edge between runs. This is the same mechanism the card
it was modelled on uses (a `linearGradient` fill plus one `animateTransform`).

The schedule is `SHINE_PATH` in `cards/hero.py`: points of (seconds after the image
loads, translation of the gradient), moved linearly in between. One pass:

| Time | Event |
| --- | --- |
| 1.5 s | light reaches "Ayham" and "Joumran" (about 128 px/s through them) |
| 3.8 s | "Ayham" is done; a quick hop (about 286 px/s) off the end of "Joumran" |
| 4.2 s | "Joumran" is done |
| 4.3 s | light reaches the photo (about 169 px/s across it) |
| 6.5 s | the photo is done |
| 7.0 s | the band is parked off the card |
| 8.0 s | the next pass starts (a pass repeats every 6.5 s) |

Speeds differ per stretch because those times cannot all be met at one constant speed.
The translations were calibrated by measuring real frames against the SVG's own clock
(`document.documentElement.getCurrentTime()`); when you change the schedule, re-measure
rather than trusting the geometry, because the faint edges of the band do not count as
light.

Rules that came out of two failed versions:

- Do not animate anything inside a `<mask>` or `<clipPath>`: Chrome does not repaint it,
  so the light never appears.
- Do not draw the light on separate overlay copies that a media query can hide. SMIL is
  not affected by `prefers-reduced-motion`, and the cards deliberately do not gate any
  animation on it, so the light plays for everyone.
- Use literal colours in gradient stops (one gradient per colour scheme, chosen by a CSS
  class), not CSS variables, and a plain animation without `additive`.
- Check any change with real-time frames, not static previews: load the SVG in headless
  Chrome over the DevTools protocol and screenshot it every ~0.5 s, with and without
  `prefers-reduced-motion` emulated.

## Fonts

Instrument Serif (display), JetBrains Mono (labels) and Inter (body) are embedded as
base64 woff2 subsets, so the cards render identically everywhere. Licences are in
`src/profile_cards/fonts/`.

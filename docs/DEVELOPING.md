# Developing the profile cards

The profile README is generated. `config.toml` says what the cards claim, `profile-cards`
fetches live data from GitHub and draws eight SVG cards into `cards/` (hero, heatmap,
activity, upstream, a title banner and one card per project), and `README.md` is
rewritten to point at them. A daily workflow refreshes everything.

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

The daily workflow needs a repository secret `PROFILE_TOKEN`: a classic personal access
token with the `read:user` scope. The built-in token cannot see private contributions, so
the workflow fails on purpose without the secret instead of publishing lower numbers.

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

Each name line is drawn twice: once normally and once in a lighter colour behind a mask.
The mask is a soft slanted band (`.sweep`, animated in `theme.py`) that glides across the
letters every few seconds. With reduced motion enabled the band rests off to the side.

## Fonts

Instrument Serif (display), JetBrains Mono (labels) and Inter (body) are embedded as
base64 woff2 subsets, so the cards render identically everywhere. Licences are in
`src/profile_cards/fonts/`.

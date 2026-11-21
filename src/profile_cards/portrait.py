"""The sketch portrait shown on the hero card, loaded from the bundled assets."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from functools import cache
from importlib import resources
from importlib.resources.abc import Traversable

INK_FILE = "portrait.webp"
FIGURE_FILE = "figure.webp"
SIZE_FILE = "portrait.json"
MEDIA_TYPE = "image/webp"


@dataclass(frozen=True)
class Portrait:
    """The portrait as two masks, ready to embed in an SVG.

    `data_uri` is the ink (ink white, paper black) and `figure_uri` is the outline of
    the person (inside white, background black); both share one size.
    """

    data_uri: str
    figure_uri: str
    width: int
    height: int

    @property
    def aspect(self) -> float:
        return self.width / self.height


def _embed(asset: Traversable) -> str:
    encoded = base64.b64encode(asset.read_bytes()).decode("ascii")
    return f"data:{MEDIA_TYPE};base64,{encoded}"


@cache
def load_portrait() -> Portrait | None:
    """The bundled portrait, or None when none has been prepared."""
    assets = resources.files("profile_cards").joinpath("assets")
    ink = assets.joinpath(INK_FILE)
    figure = assets.joinpath(FIGURE_FILE)
    size = assets.joinpath(SIZE_FILE)
    if not all(asset.is_file() for asset in (ink, figure, size)):
        return None
    dimensions = json.loads(size.read_text(encoding="utf-8"))
    return Portrait(
        data_uri=_embed(ink),
        figure_uri=_embed(figure),
        width=int(dimensions["width"]),
        height=int(dimensions["height"]),
    )

"""ASCII plants, one per growth stage.

Each plant is a list of (art, mask) rows. The mask has the same shape as the
art and picks a color per character from PALETTE, so art stays free of markup
and can be shifted around to animate swaying.
"""

from __future__ import annotations

from rich.style import Style
from rich.text import Text

from ..core.vitality import Stage

WIDTH = 11
HEIGHT = 5  # plant rows, not counting the soil

PALETTE: dict[str, Style] = {
    "g": Style(color="green"),
    "G": Style(color="bright_green", bold=True),
    "p": Style(color="magenta", bold=True),
    "y": Style(color="yellow", bold=True),
    "o": Style(color="yellow", dim=True),
    "b": Style(color="#8b5a2b"),
    "r": Style(color="red", bold=True),
    "c": Style(color="cyan"),
    "w": Style(color="white", dim=True),
    "s": Style(color="#6b4423"),
}

Row = tuple[str, str]

PLANTS: dict[Stage, list[Row]] = {
    Stage.SEED: [
        ("", ""),
        ("", ""),
        ("", ""),
        ("", ""),
        (r"     .     ", r"     y     "),
    ],
    Stage.SPROUT: [
        ("", ""),
        ("", ""),
        (r"    \ /    ", r"    G G    "),
        (r"     |     ", r"     g     "),
        (r"     |     ", r"     g     "),
    ],
    Stage.BUSH: [
        ("", ""),
        (r"   .;:;.   ", r"   GGGGG   "),
        (r"  ;:;:;:;  ", r"  GgGgGgG  "),
        (r"   ':|:'   ", r"   GGbGG   "),
        (r"     |     ", r"     b     "),
    ],
    Stage.BLOOM: [
        (r"    .-.    ", r"    ppp    "),
        (r"   ( @ )   ", r"   p y p   "),
        (r"    '-'    ", r"    ppp    "),
        (r"   \_|_/   ", r"   GgggG   "),
        (r"     |     ", r"     g     "),
    ],
    Stage.DORMANT: [
        (r"      z    ", r"      w    "),
        (r"     z     ", r"     w     "),
        (r"    (_)    ", r"    ccc    "),
        (r"    \|     ", r"    gg     "),
        (r"     |     ", r"     g     "),
    ],
    Stage.WILTED: [
        ("", ""),
        (r"    ,--.   ", r"    oooo   "),
        (r"   '    |  ", r"   o    o  "),
        (r"        |  ", r"        o  "),
        (r"        |  ", r"        o  "),
    ],
    Stage.DEAD: [
        (r"    x  x   ", r"    r  r   "),
        (r"   \  /    ", r"   b  b    "),
        (r"    \/  ,  ", r"    bb  b  "),
        (r"     |_/   ", r"     bbb   "),
        (r"     |     ", r"     b     "),
    ],
}

SOIL: Row = ("~" * WIDTH, "s" * WIDTH)

SWAY_ROWS = 3  # top rows that lean when a plant is busy


def _pad(row: Row) -> Row:
    art, mask = row
    return art.ljust(WIDTH)[:WIDTH], mask.ljust(WIDTH)[:WIDTH]


def _lean(row: Row, direction: int) -> Row:
    art, mask = row
    if direction > 0:
        return " " + art[:-1], " " + mask[:-1]
    return art[1:] + " ", mask[1:] + " "


def render_plant(stage: Stage, sway_frame: int = 0) -> Text:
    """Render a plant; sway_frame -1/0/1 leans the top rows left/none/right."""
    rows = [_pad(r) for r in PLANTS[stage]]
    if sway_frame:
        rows = [_lean(r, sway_frame) if i < SWAY_ROWS else r for i, r in enumerate(rows)]
    rows.append(SOIL)

    text = Text()
    for i, (art, mask) in enumerate(rows):
        if i:
            text.append("\n")
        for ch, key in zip(art, mask):
            text.append(ch, PALETTE.get(key))
    return text

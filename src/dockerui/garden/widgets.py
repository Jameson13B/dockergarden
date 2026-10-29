"""Garden widgets: plant tiles, beds, and the log journal."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Label, RichLog, Static

from ..core.models import ContainerInfo
from ..core.vitality import Mood, vitality
from .plants import WIDTH, render_plant

NAME_STYLE = {
    Mood.THRIVING: "bold green",
    Mood.RESTING: "dim",
    Mood.SICK: "bold red",
}


class PlantTile(Widget, can_focus=True):
    """One container, drawn as a plant with its name underneath."""

    sway_frame: reactive[int] = reactive(0)

    def __init__(self, info: ContainerInfo) -> None:
        super().__init__(id=f"plant-{info.id[:12]}")
        self.info = info

    def update_info(self, info: ContainerInfo) -> None:
        self.info = info
        self.refresh()

    def render(self) -> Text:
        v = vitality(self.info)
        text = render_plant(v.stage, self.sway_frame if v.busy else 0)
        name = self.info.name
        if len(name) > WIDTH:
            name = name[: WIDTH - 1] + "…"
        text.append("\n" + name.center(WIDTH), NAME_STYLE[v.mood])
        return text


class GardenBed(Vertical):
    """A labelled row of plants; one bed per compose project."""

    def __init__(self, title: str, bed_id: str, tiles: list[PlantTile]) -> None:
        super().__init__(id=bed_id, classes="bed")
        self.bed_title = title
        self.tiles = tiles

    def compose(self) -> ComposeResult:
        yield Label(f"🌿 {self.bed_title}", classes="bed-title")
        with Grid(classes="bed-grid"):
            yield from self.tiles


class JournalPanel(Vertical):
    """Side panel streaming a container's logs."""

    def compose(self) -> ComposeResult:
        yield Label("", id="journal-title")
        yield RichLog(id="journal-log", wrap=True, max_lines=2000, markup=False)

    def open_for(self, name: str) -> None:
        self.query_one("#journal-title", Label).update(f"📖 {name}'s growth journal  (esc to close)")
        self.query_one(RichLog).clear()

    def write_line(self, line: str) -> None:
        self.query_one(RichLog).write(Text.from_ansi(line))


class Signpost(Static):
    """Details about the selected plant."""

    def show(self, info: ContainerInfo | None) -> None:
        if info is None:
            self.update("Nothing planted yet. Run a container to grow something.")
            return
        v = vitality(info)
        parts = [
            f"[b]{info.name}[/b]",
            info.image,
            f"{info.state}" + (f" ({info.health})" if info.health else ""),
            v.stage.value,
        ]
        if info.state == "running":
            parts.append(f"cpu {info.cpu_pct:.1f}%  mem {info.mem_pct:.1f}%")
        if info.state == "exited":
            parts.append(f"exit {info.exit_code}")
        parts.append(f"[dim]{info.short_id}[/dim]")
        self.update("  ·  ".join(parts))


class ConfirmUproot(ModalScreen[bool]):
    def __init__(self, name: str) -> None:
        super().__init__()
        self.plant_name = name

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm"):
            yield Label(f"Uproot [b]{self.plant_name}[/b]? This removes the container.")
            with Horizontal(id="confirm-buttons"):
                yield Button("Uproot", variant="error", id="yes")
                yield Button("Keep it", variant="primary", id="no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

    def key_escape(self) -> None:
        self.dismiss(False)

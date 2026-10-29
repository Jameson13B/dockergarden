"""Terminal Garden: every Docker container is a plant."""

from __future__ import annotations

import asyncio
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from docker.errors import DockerException
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Footer, Header
from textual.worker import get_current_worker

from ..core.client import DockerService, Stream
from ..core.models import ContainerInfo
from ..core.vitality import vitality
from .widgets import ConfirmUproot, GardenBed, JournalPanel, PlantTile, Signpost

LOOSE_BED = "loose seeds"
TILE_WIDTH = 16  # tile width plus grid gutter
STATS_INTERVAL = 3.0
SWAY_INTERVAL = 0.4


class GardenApp(App):
    CSS_PATH = "garden.tcss"
    TITLE = "Docker Garden"

    BINDINGS = [
        Binding("enter", "journal", "Journal"),
        Binding("w", "water", "Water (start)"),
        Binding("s", "stop", "Stop"),
        Binding("p", "prune", "Prune (restart)"),
        Binding("z", "doze", "Doze (pause)"),
        Binding("u", "uproot", "Uproot (remove)"),
        Binding("escape", "close_journal", "Close journal", show=False),
        Binding("q", "quit", "Quit"),
        Binding("left,h", "move(-1, 0)", show=False),
        Binding("right,l", "move(1, 0)", show=False),
        Binding("up,k", "move(0, -1)", show=False),
        Binding("down,j", "move(0, 1)", show=False),
    ]

    def __init__(self, service: DockerService) -> None:
        super().__init__()
        self.service = service
        self._layout: tuple = ()
        self._tiles: dict[str, PlantTile] = {}
        self._columns = 6
        self._dirty = True
        self._stats_running = False
        self._apply_lock = asyncio.Lock()
        self._events: Stream | None = None
        self._log_stream: Stream | None = None
        self._sway = 1

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            yield VerticalScroll(id="garden")
            yield JournalPanel(id="journal")
        yield Signpost(id="signpost")
        yield Footer()

    def on_mount(self) -> None:
        self.watch_events()
        self.set_interval(0.5, self._reload_if_dirty)
        self.set_interval(STATS_INTERVAL, self._poll_stats)
        self.set_interval(SWAY_INTERVAL, self._sway_plants)

    def on_unmount(self) -> None:
        for stream in (self._events, self._log_stream):
            if stream:
                stream.close()

    # ── Loading the garden ────────────────────────────────────────────

    def _reload_if_dirty(self) -> None:
        if self._dirty:
            self._dirty = False
            self.load_containers()

    @work(thread=True, exclusive=True, group="list")
    def load_containers(self) -> None:
        try:
            infos = self.service.list()
        except DockerException as exc:
            self.call_from_thread(self.notify, str(exc), title="Docker", severity="error")
            return
        self.call_from_thread(self.apply_containers, infos)

    @work(thread=True, group="events")
    def watch_events(self) -> None:
        worker = get_current_worker()
        self._events = self.service.events()
        try:
            for _ in self._events:
                if worker.is_cancelled:
                    break
                self._dirty = True
        except Exception:
            pass  # stream closed on exit

    async def apply_containers(self, infos: list[ContainerInfo]) -> None:
        async with self._apply_lock:
            for info in infos:
                old = self._tiles.get(info.id)
                if old:  # keep the last stats sample until the next poll
                    info.cpu_pct, info.mem_pct = old.info.cpu_pct, old.info.mem_pct

            beds: dict[str, list[ContainerInfo]] = {}
            for info in sorted(infos, key=lambda i: i.name):
                beds.setdefault(info.compose_project or LOOSE_BED, []).append(info)
            order = sorted(beds, key=lambda b: (b == LOOSE_BED, b))
            layout = tuple((b, tuple(i.id for i in beds[b])) for b in order)

            if layout == self._layout:
                for info in infos:
                    self._tiles[info.id].update_info(info)
            else:
                first_load = not self._layout
                await self._rebuild(order, beds)
                self._layout = layout
                if first_load:
                    self._poll_stats()

            self._update_subtitle(infos)
            self._update_signpost()

    async def _rebuild(self, order: list[str], beds: dict[str, list[ContainerInfo]]) -> None:
        focused = self.focused.info.id if isinstance(self.focused, PlantTile) else None
        garden = self.query_one("#garden", VerticalScroll)
        await garden.remove_children()

        self._tiles = {}
        new_beds = []
        for n, name in enumerate(order):
            tiles = [PlantTile(info) for info in beds[name]]
            self._tiles.update((t.info.id, t) for t in tiles)
            new_beds.append(GardenBed(name, f"bed-{n}", tiles))
        await garden.mount_all(new_beds)
        self._apply_columns()

        target = self._tiles.get(focused) if focused else None
        target = target or next(iter(self._tiles.values()), None)
        if target:
            target.focus()

    def _update_subtitle(self, infos: list[ContainerInfo]) -> None:
        counts = Counter(vitality(i).stage.value for i in infos)
        self.sub_title = " · ".join(f"{n} {stage}" for stage, n in sorted(counts.items()))

    # ── Stats and animation ───────────────────────────────────────────

    def _poll_stats(self) -> None:
        if not self._stats_running:
            self._stats_running = True
            self.load_stats()

    @work(thread=True, group="stats")
    def load_stats(self) -> None:
        try:
            ids = [cid for cid, t in self._tiles.items() if t.info.state == "running"]
            if not ids:
                return

            def sample(cid: str):
                try:
                    return cid, self.service.stats(cid)
                except DockerException:
                    return cid, None

            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(sample, ids))
            self.call_from_thread(self._apply_stats, results)
        finally:
            self._stats_running = False

    def _apply_stats(self, results) -> None:
        for cid, sample in results:
            tile = self._tiles.get(cid)
            if tile and sample:
                tile.info.cpu_pct, tile.info.mem_pct = sample
                tile.refresh()
        self._update_signpost()

    def _sway_plants(self) -> None:
        self._sway = -self._sway
        for tile in self._tiles.values():
            if vitality(tile.info).busy:
                tile.sway_frame = self._sway

    # ── Layout and navigation ─────────────────────────────────────────

    def on_resize(self) -> None:
        self._apply_columns()

    def _apply_columns(self) -> None:
        width = self.query_one("#garden").size.width
        self._columns = max(1, (width - 4) // TILE_WIDTH)
        for grid in self.query(".bed-grid"):
            grid.styles.grid_size_columns = self._columns

    def on_descendant_focus(self) -> None:
        self._update_signpost()

    def _update_signpost(self) -> None:
        self.query_one(Signpost).show(self._selected())

    def _selected(self) -> ContainerInfo | None:
        return self.focused.info if isinstance(self.focused, PlantTile) else None

    def action_move(self, dx: int, dy: int) -> None:
        tiles = list(self.query(PlantTile))
        if not tiles:
            return
        current = self.focused if isinstance(self.focused, PlantTile) else tiles[0]
        index = tiles.index(current) + dx + dy * self._columns
        tiles[max(0, min(index, len(tiles) - 1))].focus()

    # ── Journal (logs) ────────────────────────────────────────────────

    def action_journal(self) -> None:
        info = self._selected()
        if not info:
            return
        self._stop_log_stream()
        journal = self.query_one(JournalPanel)
        journal.add_class("open")
        journal.open_for(info.name)
        self.stream_logs(info.id)
        self.call_after_refresh(self._apply_columns)

    def action_close_journal(self) -> None:
        self._stop_log_stream()
        self.query_one(JournalPanel).remove_class("open")
        self.call_after_refresh(self._apply_columns)

    def _stop_log_stream(self) -> None:
        self.workers.cancel_group(self, "logs")
        if self._log_stream:
            self._log_stream.close()
            self._log_stream = None

    @work(thread=True, exclusive=True, group="logs")
    def stream_logs(self, container_id: str) -> None:
        worker = get_current_worker()
        journal = self.query_one(JournalPanel)
        try:
            stream = self._log_stream = self.service.logs(container_id)
            buffer = ""
            for chunk in stream:
                if worker.is_cancelled:
                    break
                buffer += chunk
                *lines, buffer = buffer.split("\n")
                for line in lines:
                    self.call_from_thread(journal.write_line, line)
            if buffer and not worker.is_cancelled:
                self.call_from_thread(journal.write_line, buffer)
        except Exception as exc:
            if not worker.is_cancelled:
                self.call_from_thread(journal.write_line, f"[journal closed: {exc}]")

    # ── Gardening actions ─────────────────────────────────────────────

    def action_water(self) -> None:
        self._act("start", "Watering")

    def action_stop(self) -> None:
        self._act("stop", "Stopping")

    def action_prune(self) -> None:
        self._act("restart", "Pruning")

    def action_doze(self) -> None:
        info = self._selected()
        if info and info.state == "paused":
            self._act("unpause", "Waking")
        elif info and info.state == "running":
            self._act("pause", "Putting to sleep")
        elif info:
            self.notify(f"{info.name} isn't growing, so it can't doze.", severity="warning")

    def action_uproot(self) -> None:
        info = self._selected()
        if not info:
            return

        def confirmed(yes: bool | None) -> None:
            if yes:
                self._act("remove", "Uprooting", info)

        self.push_screen(ConfirmUproot(info.name), confirmed)

    def _act(self, verb: str, label: str, info: ContainerInfo | None = None) -> None:
        info = info or self._selected()
        if info:
            self.notify(f"{label} {info.name}…")
            self.run_action_worker(verb, info)

    @work(thread=True, group="actions")
    def run_action_worker(self, verb: str, info: ContainerInfo) -> None:
        try:
            getattr(self.service, verb)(info.id)
        except DockerException as exc:
            self.call_from_thread(
                self.notify, str(exc), title=f"Couldn't {verb} {info.name}", severity="error"
            )
        self._dirty = True


def main() -> None:
    try:
        service = DockerService()
        service.client.ping()
    except DockerException as exc:
        sys.exit(f"Can't reach Docker: {exc}")
    GardenApp(service).run()


if __name__ == "__main__":
    main()

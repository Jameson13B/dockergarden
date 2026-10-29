"""Plain data describing a container, independent of any UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ContainerInfo:
    id: str
    name: str
    image: str
    state: str  # created, running, paused, restarting, removing, exited, dead
    health: str | None = None  # healthy, unhealthy, starting, or None
    exit_code: int = 0
    started_at: datetime | None = None
    compose_project: str | None = None
    cpu_pct: float = 0.0
    mem_pct: float = 0.0
    labels: dict[str, str] = field(default_factory=dict)

    @property
    def short_id(self) -> str:
        return self.id[:12]

    def uptime_seconds(self, now: datetime | None = None) -> float:
        if self.state != "running" or self.started_at is None:
            return 0.0
        now = now or datetime.now(timezone.utc)
        return max(0.0, (now - self.started_at).total_seconds())

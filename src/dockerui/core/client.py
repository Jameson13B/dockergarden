"""Thin wrapper around the Docker SDK.

Every call here is blocking; UIs should run them in worker threads.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

import docker
from docker.models.containers import Container

from .models import ContainerInfo

COMPOSE_PROJECT_LABEL = "com.docker.compose.project"


def _parse_time(value: str | None) -> datetime | None:
    if not value or value.startswith("0001-"):
        return None
    # Docker uses RFC3339 with nanoseconds; trim to microseconds for fromisoformat.
    value = value.replace("Z", "+00:00")
    if "." in value:
        head, rest = value.split(".", 1)
        frac, tz = rest[:-6], rest[-6:]
        value = f"{head}.{frac[:6]}{tz}"
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _to_info(container: Container) -> ContainerInfo:
    attrs = container.attrs
    state = attrs.get("State", {})
    labels = container.labels or {}
    image = attrs.get("Config", {}).get("Image") or ""
    return ContainerInfo(
        id=container.id,
        name=container.name,
        image=image,
        state=state.get("Status", container.status),
        health=(state.get("Health") or {}).get("Status"),
        exit_code=state.get("ExitCode", 0),
        started_at=_parse_time(state.get("StartedAt")),
        compose_project=labels.get(COMPOSE_PROJECT_LABEL),
        labels=labels,
    )


def _cpu_mem_pct(stats: dict) -> tuple[float, float]:
    cpu, precpu = stats.get("cpu_stats", {}), stats.get("precpu_stats", {})
    cpu_delta = cpu.get("cpu_usage", {}).get("total_usage", 0) - precpu.get(
        "cpu_usage", {}
    ).get("total_usage", 0)
    sys_delta = cpu.get("system_cpu_usage", 0) - precpu.get("system_cpu_usage", 0)
    cpus = cpu.get("online_cpus") or 1
    cpu_pct = (cpu_delta / sys_delta) * cpus * 100 if sys_delta > 0 else 0.0

    mem = stats.get("memory_stats", {})
    limit = mem.get("limit") or 0
    usage = mem.get("usage", 0) - mem.get("stats", {}).get("inactive_file", 0)
    mem_pct = (usage / limit) * 100 if limit else 0.0
    return max(cpu_pct, 0.0), max(mem_pct, 0.0)


class Stream:
    """A blocking iterator that another thread can close() to unblock it."""

    def __init__(self, raw) -> None:
        self._raw = raw

    def __iter__(self) -> Iterator:
        for item in self._raw:
            yield item.decode("utf-8", errors="replace") if isinstance(item, bytes) else item

    def close(self) -> None:
        try:
            self._raw.close()
        except Exception:
            pass


class DockerService:
    def __init__(self, client: docker.DockerClient | None = None) -> None:
        self.client = client or docker.from_env()

    def list(self) -> list[ContainerInfo]:
        return [_to_info(c) for c in self.client.containers.list(all=True)]

    def stats(self, container_id: str) -> tuple[float, float]:
        """Return (cpu_pct, mem_pct) from a single stats sample."""
        raw = self.client.api.stats(container_id, stream=False)
        return _cpu_mem_pct(raw)

    def logs(self, container_id: str, follow: bool = True, tail: int = 200) -> Stream:
        raw = self.client.api.logs(
            container_id, stream=True, follow=follow, tail=tail, timestamps=False
        )
        return Stream(raw)

    def events(self) -> Stream:
        """Container lifecycle events; iterating blocks until close()."""
        return Stream(self.client.events(decode=True, filters={"type": "container"}))

    def _get(self, container_id: str) -> Container:
        return self.client.containers.get(container_id)

    def start(self, container_id: str) -> None:
        self._get(container_id).start()

    def stop(self, container_id: str) -> None:
        self._get(container_id).stop(timeout=10)

    def restart(self, container_id: str) -> None:
        self._get(container_id).restart(timeout=10)

    def pause(self, container_id: str) -> None:
        self._get(container_id).pause()

    def unpause(self, container_id: str) -> None:
        self._get(container_id).unpause()

    def remove(self, container_id: str) -> None:
        self._get(container_id).remove(force=True)

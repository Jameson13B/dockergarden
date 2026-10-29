"""Map a container's condition to a front-end-neutral "vitality".

The garden reads it as plant growth; the solar system can read the same
values as planet size, orbit speed and so on.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .models import ContainerInfo

SPROUT_MAX_SECONDS = 10 * 60
BUSH_MAX_SECONDS = 60 * 60
BUSY_CPU_PCT = 50.0


class Stage(str, Enum):
    SEED = "seed"  # created, never started
    SPROUT = "sprout"
    BUSH = "bush"
    BLOOM = "bloom"
    DORMANT = "dormant"  # paused
    WILTED = "wilted"  # exited cleanly
    DEAD = "dead"  # crashed, dead, or unhealthy


class Mood(str, Enum):
    THRIVING = "thriving"
    RESTING = "resting"
    SICK = "sick"


@dataclass(frozen=True)
class Vitality:
    stage: Stage
    mood: Mood
    busy: bool  # high CPU: the garden sways, the solar system spins faster


def vitality(info: ContainerInfo, now: datetime | None = None) -> Vitality:
    busy = info.state == "running" and info.cpu_pct >= BUSY_CPU_PCT

    if info.health == "unhealthy" or info.state == "dead":
        return Vitality(Stage.DEAD, Mood.SICK, busy)
    if info.state == "paused":
        return Vitality(Stage.DORMANT, Mood.RESTING, False)
    if info.state == "created":
        return Vitality(Stage.SEED, Mood.RESTING, False)
    if info.state in ("exited", "removing"):
        if info.exit_code == 0:
            return Vitality(Stage.WILTED, Mood.RESTING, False)
        return Vitality(Stage.DEAD, Mood.SICK, False)
    if info.state == "restarting":
        return Vitality(Stage.SPROUT, Mood.SICK, busy)

    uptime = info.uptime_seconds(now)
    if uptime < SPROUT_MAX_SECONDS:
        stage = Stage.SPROUT
    elif uptime < BUSH_MAX_SECONDS:
        stage = Stage.BUSH
    else:
        stage = Stage.BLOOM
    return Vitality(stage, Mood.THRIVING, busy)

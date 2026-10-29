from datetime import datetime, timedelta, timezone

import pytest

from dockerui.core.models import ContainerInfo
from dockerui.core.vitality import Mood, Stage, vitality

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


def make(state="running", uptime=None, **kw) -> ContainerInfo:
    started = NOW - timedelta(seconds=uptime) if uptime is not None else None
    return ContainerInfo(id="abc", name="c", image="img", state=state, started_at=started, **kw)


@pytest.mark.parametrize(
    "uptime, stage",
    [(30, Stage.SPROUT), (20 * 60, Stage.BUSH), (2 * 3600, Stage.BLOOM)],
)
def test_running_grows_with_uptime(uptime, stage):
    v = vitality(make(uptime=uptime), now=NOW)
    assert v.stage == stage
    assert v.mood == Mood.THRIVING


def test_paused_is_dormant():
    assert vitality(make("paused", uptime=999), now=NOW).stage == Stage.DORMANT


def test_clean_exit_wilts():
    assert vitality(make("exited", exit_code=0), now=NOW).stage == Stage.WILTED


def test_crash_dies():
    v = vitality(make("exited", exit_code=1), now=NOW)
    assert v.stage == Stage.DEAD
    assert v.mood == Mood.SICK


def test_unhealthy_dies_even_when_running():
    assert vitality(make(uptime=5000, health="unhealthy"), now=NOW).stage == Stage.DEAD


def test_created_is_seed():
    assert vitality(make("created"), now=NOW).stage == Stage.SEED


def test_busy_only_when_running():
    assert vitality(make(uptime=60, cpu_pct=90), now=NOW).busy
    assert not vitality(make("exited", cpu_pct=90), now=NOW).busy

"""Nhịp tim worker: liveness probe trên K8s (eduassist-worker-alive) khởi động lại worker khi vòng lặp treo."""

import os
import time

import pytest

from eduassist.background import runner
from eduassist.config import get_settings


@pytest.fixture
def hb(tmp_path, monkeypatch):
    path = tmp_path / "alive"
    monkeypatch.setenv("WORKER_HEARTBEAT_FILE", str(path))
    monkeypatch.setenv("WORKER_POLL_SECONDS", "5")
    monkeypatch.setenv("WORKER_HEARTBEAT_GRACE_SECONDS", "60")
    get_settings.cache_clear()
    yield path
    get_settings.cache_clear()


def _exit_code() -> int:
    with pytest.raises(SystemExit) as e:
        runner.heartbeat_ok()
    return e.value.code


def test_missing_heartbeat_fails(hb):
    assert _exit_code() == 1


def test_fresh_heartbeat_passes(hb):
    runner.beat()
    assert hb.exists()
    assert _exit_code() == 0


def test_stale_heartbeat_fails(hb):
    runner.beat()
    old = time.time() - 600
    os.utime(hb, (old, old))
    assert _exit_code() == 1

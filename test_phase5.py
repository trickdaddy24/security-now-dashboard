"""Phase 5 offline tests — auth, lock, circuit, cleanup, metrics, rate limit."""

from __future__ import annotations

import base64
import os
import tempfile
import time
from pathlib import Path

from starlette.testclient import TestClient

from grc_downloader.auth import SecurityMiddleware, check_api_key, check_basic_auth
from grc_downloader.circuit import CircuitBreaker
from grc_downloader.cleanup import cleanup_stale_parts
from grc_downloader.lockfile import DownloadDirLock
from grc_downloader.metrics import render_prometheus
from grc_downloader.ratelimit import RateLimiter


def test_circuit_breaker_opens_and_resets() -> None:
    cb = CircuitBreaker(failure_threshold=2, reset_seconds=0.1)
    assert not cb.is_open()
    cb.record_failure()
    cb.record_failure()
    assert cb.is_open()
    time.sleep(0.15)
    assert not cb.is_open()


def test_download_dir_lock_exclusive() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        a = DownloadDirLock(root)
        b = DownloadDirLock(root)
        assert a.acquire() is True
        assert b.acquire() is False
        assert a.holder_pid() == os.getpid()
        a.release()
        assert b.acquire() is True
        b.release()


def test_cleanup_stale_parts() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        old = root / "sn-0001.mp3.part"
        old.write_text("partial", encoding="utf-8")
        old_time = time.time() - 10 * 86400
        os.utime(old, (old_time, old_time))
        fresh = root / "sn-0002.mp3.part"
        fresh.write_text("fresh", encoding="utf-8")
        removed = cleanup_stale_parts(root, max_age_days=7)
        assert "sn-0001.mp3.part" in removed
        assert fresh.is_file()


def test_metrics_render() -> None:
    body = render_prometheus(
        {"running": True, "counts": {"active": 2, "failed": 1, "completed": 5}, "bytes_completed": 4096},
        latest_episode=1086,
        errors_total=3,
    )
    assert "sn_jobs_active 2" in body
    assert "sn_last_episode_number 1086" in body
    assert "sn_errors_total 3" in body
    assert "sn_batch_running 1" in body


def test_rate_limiter() -> None:
    rl = RateLimiter(max_per_minute=2)
    assert rl.allow("ip1") is True
    assert rl.allow("ip1") is True
    assert rl.allow("ip1") is False
    assert rl.allow("ip2") is True


def test_auth_helpers() -> None:
    class Req:
        def __init__(self, headers: dict[str, str]):
            self.headers = headers

    token = base64.b64encode(b"user:pass").decode()
    assert check_basic_auth(Req({"Authorization": f"Basic {token}"}), "user", "pass")
    assert not check_basic_auth(Req({}), "user", "pass")
    assert check_api_key(Req({"X-SN-API-Key": "secret"}), "secret")
    assert not check_api_key(Req({}), "secret")


def test_security_middleware_blocks_when_configured() -> None:
    os.environ["SN_DEV_MODE"] = "0"
    os.environ["SN_AUTH_USER"] = "admin"
    os.environ["SN_AUTH_PASSWORD"] = "testpass"
    try:
        import importlib
        import app as app_module

        importlib.reload(app_module)
        client = TestClient(app_module.app)
        assert client.get("/health").status_code == 200
        assert client.get("/metrics").status_code == 200
        assert client.get("/api/status").status_code == 401
        token = base64.b64encode(b"admin:testpass").decode()
        assert client.get("/api/status", headers={"Authorization": f"Basic {token}"}).status_code == 200
    finally:
        os.environ.pop("SN_DEV_MODE", None)
        os.environ.pop("SN_AUTH_USER", None)
        os.environ.pop("SN_AUTH_PASSWORD", None)
        import importlib
        import app as app_module

        os.environ["SN_DEV_MODE"] = "1"
        importlib.reload(app_module)


if __name__ == "__main__":
    test_circuit_breaker_opens_and_resets()
    test_download_dir_lock_exclusive()
    test_cleanup_stale_parts()
    test_metrics_render()
    test_rate_limiter()
    test_auth_helpers()
    test_security_middleware_blocks_when_configured()
    print("phase5 ok")
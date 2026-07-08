"""CLI smoke tests — no network required."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from grc_downloader.cli import (
    EXIT_OK,
    EXIT_PARTIAL,
    _exit_from_counts,
    build_parser,
    collect_media,
    resolve_episode_spec,
)
from grc_downloader.client_tokens import claim_token, lookup_token
from grc_downloader.config import AppConfig
from grc_downloader.history import read_batches


def _args(**kwargs) -> argparse.Namespace:
    base = {
        "ep": None,
        "latest": False,
        "all": False,
        "download_dir": None,
        "parallel": None,
        "filename_format": None,
        "pretend": False,
        "quiet": False,
        "skip_digital_cert_check": False,
        "update_check": False,
        "json": False,
        "retry_failed": False,
        "ahq": False,
        "alq": False,
        "atwit": False,
        "vhd": False,
        "vhq": False,
        "vlq": False,
        "eptxt": False,
        "eppdf": False,
        "ephtml": False,
        "epnotes": False,
    }
    base.update(kwargs)
    return argparse.Namespace(**base)


def test_resolve_episode_spec() -> None:
    assert resolve_episode_spec(_args()) == "next"
    assert resolve_episode_spec(_args(latest=True)) == "latest"
    assert resolve_episode_spec(_args(all=True)) == "all"
    assert resolve_episode_spec(_args(ep="1080:1086")) == "1080:1086"


def test_collect_media_flags() -> None:
    cfg = AppConfig(default_media=["audio_hq"])
    media = collect_media(_args(ahq=True, epnotes=True), cfg)
    assert [m.value for m in media] == ["audio_hq", "show_notes"]


def test_collect_media_defaults() -> None:
    cfg = AppConfig(default_media=["show_notes"])
    media = collect_media(_args(), cfg)
    assert [m.value for m in media] == ["show_notes"]


def test_exit_codes() -> None:
    assert _exit_from_counts({"failed": 0, "completed": 3}) == EXIT_OK
    assert _exit_from_counts({"failed": 1, "completed": 2}) == EXIT_PARTIAL


def test_parser_has_upstream_flags() -> None:
    parser = build_parser()
    options: set[str] = set()
    for action in parser._actions:
        if action.option_strings:
            options.update(action.option_strings)
    for flag in ("-ep", "-latest", "-all", "-ahq", "-epnotes", "-p", "-q", "-u", "--json"):
        assert flag in options


def test_client_tokens() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        is_new, existing = claim_token(root, "cron-1", "batch-a")
        assert is_new is True
        assert existing is None
        assert lookup_token(root, "cron-1") == "batch-a"
        is_new, existing = claim_token(root, "cron-1", "batch-b")
        assert is_new is False
        assert existing == "batch-a"


def test_read_batches() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "history.jsonl"
        path.write_text(
            "\n".join([
                json.dumps({
                    "type": "batch_started",
                    "batch_id": "b1",
                    "ts": 1.0,
                    "episodes": [1086],
                    "media": ["audio_hq"],
                }),
                json.dumps({
                    "type": "batch_finished",
                    "batch_id": "b1",
                    "ts": 2.0,
                    "counts": {"completed": 1, "failed": 0},
                }),
            ]),
            encoding="utf-8",
        )
        batches = read_batches(path, limit=5)
        assert len(batches) == 1
        assert batches[0]["batch_id"] == "b1"
        assert batches[0]["counts"]["completed"] == 1


if __name__ == "__main__":
    test_resolve_episode_spec()
    test_collect_media_flags()
    test_collect_media_defaults()
    test_exit_codes()
    test_parser_has_upstream_flags()
    test_client_tokens()
    test_read_batches()
    print("cli ok")
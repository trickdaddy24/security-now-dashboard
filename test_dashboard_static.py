"""Static dashboard asset checks — no server required."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"


def test_index_has_aria_and_version() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'id="versionBadge"' in html
    assert "topbar-right" in html
    assert 'id="episodeGrid"' in html
    assert 'aria-label="Download jobs"' in html
    assert "manifest.json" in html
    assert 'data-tab="insights"' in html


def test_manifest_exists() -> None:
    assert (STATIC / "manifest.json").is_file()
    assert (STATIC / "icon.svg").is_file()


if __name__ == "__main__":
    test_index_has_aria_and_version()
    test_manifest_exists()
    print("dashboard static ok")
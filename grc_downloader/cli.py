"""Headless CLI — parity with GRC-Downloader.sh flags."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from .config import AppConfig, load_config
from .disk import check_disk_space
from .downloader import DownloadManager
from .models import JobStatus, MediaType
from .library import library_summary
from .parser import fetch_catalog, parse_episode_range
from .rss import build_feeds
from .search import index_transcripts, search_transcripts
from .update import check_for_update

EXIT_OK = 0
EXIT_PARTIAL = 1
EXIT_USAGE = 2
EXIT_DISK = 3

MEDIA_FLAGS: dict[str, MediaType] = {
    "ahq": MediaType.AUDIO_HQ,
    "alq": MediaType.AUDIO_LQ,
    "atwit": MediaType.AUDIO_TWIT,
    "vhd": MediaType.VIDEO_HD,
    "vhq": MediaType.VIDEO_HQ,
    "vlq": MediaType.VIDEO_LQ,
    "eptxt": MediaType.TRANSCRIPT_TXT,
    "eppdf": MediaType.TRANSCRIPT_PDF,
    "ephtml": MediaType.TRANSCRIPT_HTML,
    "epnotes": MediaType.SHOW_NOTES,
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sn-download",
        description="Download Security Now episodes (fork of GRC-Downloader.sh)",
    )
    p.add_argument("-ep", "--ep", metavar="SPEC", help="Episode spec: N, N:M, N:latest")
    p.add_argument("-latest", action="store_true", help="Download the latest episode")
    p.add_argument("-all", action="store_true", help="Download all episodes")
    for short, media in MEDIA_FLAGS.items():
        p.add_argument(f"-{short}", action="store_true", help=f"Download {media.value}")
    p.add_argument("-d", "--download-dir", metavar="PATH", help="Download directory")
    p.add_argument("-pd", "--parallel", type=int, metavar="N", help="Parallel downloads (1-8)")
    p.add_argument("-ff", "--filename-format", choices=["raw", "ordered", "kodi"], help="Filename preset")
    p.add_argument("-p", "--pretend", action="store_true", help="Dry run — list jobs only")
    p.add_argument("-q", "--quiet", action="store_true", help="Suppress progress on stderr")
    p.add_argument(
        "-skip-digital-cert-check",
        action="store_true",
        help="Disable TLS certificate verification",
    )
    p.add_argument("-u", "--update-check", action="store_true", help="Check GitHub for newer release")
    p.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    p.add_argument("--retry-failed", action="store_true", help="Re-queue failed jobs from last batch")
    p.add_argument("-create-rss-feeds", dest="create_rss_feeds", action="store_true", help="Build all RSS feeds")
    p.add_argument("-create-rss-audio", dest="create_rss_audio", action="store_true", help="Build audio RSS")
    p.add_argument("-create-rss-video", dest="create_rss_video", action="store_true", help="Build video RSS")
    p.add_argument("-create-rss-text", dest="create_rss_text", action="store_true", help="Build text RSS")
    p.add_argument("-rss-limit", dest="rss_limit", type=int, metavar="N", help="RSS description char limit")
    p.add_argument("-stxt", metavar="QUERY", help="Search local transcripts")
    p.add_argument("-dandstxt", metavar="QUERY", help="Download missing transcripts, then search")
    p.add_argument("--reindex-search", dest="reindex_search", action="store_true", help="Rebuild transcript search index")
    return p


def _apply_env_defaults(args: argparse.Namespace) -> None:
    if not args.ep and os.getenv("SN_EPISODES"):
        args.ep = os.getenv("SN_EPISODES")
    if not args.latest and os.getenv("SN_LATEST", "").lower() in ("1", "true", "yes"):
        args.latest = True
    if not args.all and os.getenv("SN_ALL", "").lower() in ("1", "true", "yes"):
        args.all = True
    if not args.download_dir and os.getenv("SN_DOWNLOAD_DIR"):
        args.download_dir = os.getenv("SN_DOWNLOAD_DIR")
    if args.parallel is None and os.getenv("SN_PARALLEL"):
        args.parallel = int(os.getenv("SN_PARALLEL"))
    if not args.filename_format and os.getenv("SN_FILENAME_FORMAT"):
        args.filename_format = os.getenv("SN_FILENAME_FORMAT")
    if not args.pretend and os.getenv("SN_PRETEND", "").lower() in ("1", "true", "yes"):
        args.pretend = True
    if not args.quiet and os.getenv("SN_QUIET", "").lower() in ("1", "true", "yes"):
        args.quiet = True
    if not args.json and os.getenv("SN_JSON", "").lower() in ("1", "true", "yes"):
        args.json = True
    if not args.retry_failed and os.getenv("SN_RETRY_FAILED", "").lower() in ("1", "true", "yes"):
        args.retry_failed = True
    if not args.update_check and os.getenv("SN_UPDATE_CHECK", "").lower() in ("1", "true", "yes"):
        args.update_check = True
    if os.getenv("SN_SKIP_SSL", "").lower() in ("1", "true", "yes"):
        args.skip_digital_cert_check = True

    media_env = os.getenv("SN_MEDIA", "")
    if media_env:
        for token in media_env.replace(",", " ").split():
            norm = token.strip().lower()
            key = MEDIA_ENV_MAP.get(norm, norm)
            if key in MEDIA_FLAGS:
                setattr(args, key, True)


def resolve_episode_spec(args: argparse.Namespace) -> str:
    if args.latest:
        return "latest"
    if args.all:
        return "all"
    if args.ep:
        return args.ep.strip()
    return "next"


def collect_media(args: argparse.Namespace, config: AppConfig) -> list[MediaType]:
    selected = [media for key, media in MEDIA_FLAGS.items() if getattr(args, key, False)]
    if selected:
        return selected
    return [MediaType(m) for m in config.default_media]


def apply_cli_overrides(config: AppConfig, args: argparse.Namespace) -> AppConfig:
    if args.download_dir:
        config.download_dir = Path(args.download_dir).expanduser()
    if args.parallel is not None:
        config.parallel = max(1, min(8, args.parallel))
    if args.filename_format:
        config.filename_format = args.filename_format
    if args.skip_digital_cert_check:
        config.verify_ssl = False
    config.download_dir.mkdir(parents=True, exist_ok=True)
    return config


def make_progress_printer(quiet: bool, json_mode: bool):
    async def broadcast(message: dict[str, Any]) -> None:
        if quiet or json_mode:
            return
        event = message.get("event")
        data = message.get("data") or {}
        if event == "job_updated" and "job" in data:
            job = data["job"]
            if job.get("status") == JobStatus.RUNNING.value:
                pct = job.get("percent")
                pct_s = f"{pct:.0f}%" if pct is not None else "—"
                speed = job.get("speed_human", "—")
                sys.stderr.write(
                    f"\r  ep {job['episode']:4d} {job['media']:<16} {pct_s:>5} {speed:>10}"
                )
                sys.stderr.flush()
            elif job.get("status") in {
                JobStatus.COMPLETED.value,
                JobStatus.FAILED.value,
                JobStatus.SKIPPED.value,
            }:
                status = job["status"]
                err = f" — {job['error']}" if job.get("error") else ""
                sys.stderr.write(f"\r  ep {job['episode']:4d} {job['media']:<16} {status}{err}\n")
                sys.stderr.flush()
        elif event == "batch_finished":
            counts = data.get("counts") or {}
            sys.stderr.write(
                f"Batch done: {counts.get('completed', 0)} completed, "
                f"{counts.get('failed', 0)} failed\n"
            )
            sys.stderr.flush()

    return broadcast


MEDIA_ENV_MAP: dict[str, str] = {media.value: key for key, media in MEDIA_FLAGS.items()}


def _has_download_intent(args: argparse.Namespace) -> bool:
    return any([
        args.ep,
        args.latest,
        args.all,
        args.retry_failed,
        *[getattr(args, k) for k in MEDIA_FLAGS],
    ])


def _has_library_intent(args: argparse.Namespace) -> bool:
    return any([
        args.create_rss_feeds,
        args.create_rss_audio,
        args.create_rss_video,
        args.create_rss_text,
        args.stxt,
        args.dandstxt,
        args.reindex_search,
    ])


async def _download_missing_transcripts(config: AppConfig, mgr: DownloadManager) -> int:
    _, latest = await fetch_catalog(verify_ssl=config.verify_ssl)
    summary = library_summary(config.download_dir, latest)
    episodes = [
        item["episode"]
        for item in summary.get("missing_formats", [])
        if "transcript_txt" in item.get("missing", [])
    ]
    if not episodes:
        return EXIT_OK
    episodes_meta, _ = await fetch_catalog(verify_ssl=config.verify_ssl)
    titles = {e.number: e.title for e in episodes_meta}
    dates = {e.number: e.date_label for e in episodes_meta}
    ok, err = await mgr.enqueue(
        episodes=sorted(set(episodes)),
        media_types=[MediaType.TRANSCRIPT_TXT],
        titles=titles,
        dates=dates,
    )
    if not ok:
        print(err or "Failed to queue transcripts", file=sys.stderr)
        return EXIT_USAGE
    while mgr._running:  # noqa: SLF001
        await asyncio.sleep(0.25)
    return _exit_from_counts(mgr.snapshot()["counts"])


async def run_cli(args: argparse.Namespace) -> int:
    config = apply_cli_overrides(load_config(), args)
    quiet = args.quiet
    json_mode = args.json
    if args.rss_limit is not None:
        config.rss_limit = args.rss_limit

    if args.reindex_search:
        state = index_transcripts(config.download_dir, db_path=config.resolve_search_db())
        if json_mode:
            print(json.dumps(state))
        else:
            print(f"Indexed {state['documents']} transcript(s)")
        if not _has_download_intent(args) and not any([
            args.create_rss_feeds,
            args.create_rss_audio,
            args.create_rss_video,
            args.create_rss_text,
            args.stxt,
            args.dandstxt,
        ]):
            return EXIT_OK

    rss_which: set[str] = set()
    if args.create_rss_feeds:
        rss_which = {"audio", "video", "text", "all"}
    else:
        if args.create_rss_audio:
            rss_which.add("audio")
        if args.create_rss_video:
            rss_which.add("video")
        if args.create_rss_text:
            rss_which.add("text")
    if rss_which:
        base = config.rss_base_url or os.getenv("SN_PUBLIC_URL")
        state = build_feeds(
            config.download_dir,
            rss_dir=config.resolve_rss_dir(),
            base_url=base,
            desc_limit=config.rss_limit,
            which=rss_which,
        )
        if json_mode:
            print(json.dumps(state))
        else:
            for key, count in (state.get("counts") or {}).items():
                print(f"RSS {key}: {count} item(s)")
        if not _has_download_intent(args) and not (args.stxt or args.dandstxt):
            return EXIT_OK

    if args.stxt or args.dandstxt:
        query = args.dandstxt or args.stxt
        mgr = DownloadManager(config, broadcast=make_progress_printer(quiet, json_mode))
        if args.dandstxt:
            code = await _download_missing_transcripts(config, mgr)
            if code != EXIT_OK:
                return code
        index_transcripts(config.download_dir, db_path=config.resolve_search_db())
        results = search_transcripts(
            config.download_dir,
            query,
            db_path=config.resolve_search_db(),
        )
        if json_mode:
            print(json.dumps({"query": query, "results": results}))
        else:
            if not results:
                print("No matches.")
            for hit in results:
                print(f"#{hit['episode']} {hit['title']}")
                if hit.get("snippet"):
                    print(f"  {hit['snippet'].replace('<mark>', '*').replace('</mark>', '*')}")
        return EXIT_OK

    if args.update_check:
        info = await check_for_update()
        if json_mode:
            print(json.dumps(info))
        elif info.get("update_available"):
            print(f"Update available: v{info['latest']} (current v{info['current']}) — {info['url']}")
        elif info.get("error"):
            print(f"Update check failed: {info['error']}", file=sys.stderr)
        else:
            print(f"Up to date (v{info['current']})")
        if not _has_download_intent(args):
            return EXIT_OK

    media_types = collect_media(args, config)
    if not media_types and not args.retry_failed:
        print("No media types selected. Use -ahq, -epnotes, etc.", file=sys.stderr)
        return EXIT_USAGE

    mgr = DownloadManager(config, broadcast=make_progress_printer(quiet, json_mode))

    if args.retry_failed:
        ok, err = await mgr.enqueue(episodes=[], media_types=[], retry_failed=True)
        if not ok:
            print(err or "Retry failed", file=sys.stderr)
            return EXIT_USAGE
        while mgr._running:  # noqa: SLF001
            await asyncio.sleep(0.25)
        snap = mgr.snapshot()
        if json_mode:
            print(json.dumps(snap))
        return _exit_from_counts(snap["counts"])

    episodes_meta, latest = await fetch_catalog(verify_ssl=config.verify_ssl)
    titles = {e.number: e.title for e in episodes_meta}
    dates = {e.number: e.date_label for e in episodes_meta}
    local_next = mgr._local_next_episode()  # noqa: SLF001

    ep_spec = resolve_episode_spec(args)
    ep_list = parse_episode_range(ep_spec, latest, local_next)
    if not ep_list:
        print(f"No episodes matched spec '{ep_spec}' (latest={latest})", file=sys.stderr)
        return EXIT_USAGE

    if args.pretend:
        tasks = mgr.build_tasks(
            ep_list,
            media_types,
            titles=titles,
            dates=dates,
            filename_format=config.filename_format,
        )
        payload = {
            "pretend": True,
            "episodes": ep_list,
            "media": [m.value for m in media_types],
            "jobs": [
                {"episode": t.episode, "media": t.media.value, "filename": t.filename, "url": t.url}
                for t in tasks
            ],
        }
        if json_mode:
            print(json.dumps(payload))
        else:
            print(f"Pretend: {len(tasks)} job(s) for episodes {ep_list[0]}…{ep_list[-1]}")
            for t in tasks:
                print(f"  {t.filename}  ←  {t.url}")
        return EXIT_OK

    ok, msg = check_disk_space(config.download_dir, ep_list, media_types, config.min_free_mb)
    if not ok:
        print(msg, file=sys.stderr)
        return EXIT_DISK

    ok, err = await mgr.enqueue(
        episodes=ep_list,
        media_types=media_types,
        titles=titles,
        dates=dates,
        parallel=config.parallel,
        filename_format=config.filename_format,
    )
    if not ok:
        print(err or "Enqueue failed", file=sys.stderr)
        if "disk" in (err or "").lower() or "space" in (err or "").lower():
            return EXIT_DISK
        return EXIT_USAGE

    if not quiet and not json_mode:
        sys.stderr.write(f"Downloading {len(ep_list)} episode(s), {len(media_types)} format(s) each\n")

    while mgr._running:  # noqa: SLF001
        await asyncio.sleep(0.25)

    snap = mgr.snapshot()
    if json_mode:
        print(json.dumps(snap))
    return _exit_from_counts(snap["counts"])


def _exit_from_counts(counts: dict[str, int]) -> int:
    failed = counts.get("failed", 0)
    if failed:
        return EXIT_PARTIAL
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return EXIT_USAGE if exc.code not in (0, None) else EXIT_OK

    _apply_env_defaults(args)

    try:
        return asyncio.run(run_cli(args))
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return EXIT_PARTIAL
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
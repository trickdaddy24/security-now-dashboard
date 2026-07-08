from __future__ import annotations

from pathlib import Path


def episode_folder_name(episode: int) -> str:
    return f"sn-{episode:04d}"


def episode_dir(download_dir: Path, episode: int, *, episode_folders: bool) -> Path:
    base = Path(download_dir)
    if episode_folders:
        return base / episode_folder_name(episode)
    return base


def media_storage_path(
    download_dir: Path,
    episode: int,
    filename: str,
    *,
    episode_folders: bool,
) -> Path:
    if episode_folders:
        return episode_dir(download_dir, episode, episode_folders=True) / filename
    return Path(download_dir) / filename


def media_rel_path(episode: int, filename: str, *, episode_folders: bool) -> str:
    if episode_folders:
        return f"{episode_folder_name(episode)}/{filename}"
    return filename
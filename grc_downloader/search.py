from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

from .library import _episode_from_name

INDEX_STATE_FILE = ".sn-search-index.json"
DEFAULT_DB_NAME = ".sn-search.db"

EPISODE_FILE_RE = re.compile(r"sn-(\d{4})\.txt$", re.I)


def _db_path(download_dir: Path, db_path: Path | None) -> Path:
    return db_path if db_path else download_dir / DEFAULT_DB_NAME


def _connect(db_file: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS transcripts USING fts5("
        "episode UNINDEXED, title, content, tokenize='porter unicode61'"
        ")"
    )
    conn.commit()


def index_transcripts(download_dir: Path, db_path: Path | None = None) -> dict[str, Any]:
    download_dir = Path(download_dir)
    db_file = _db_path(download_dir, db_path)
    conn = _connect(db_file)
    _init_schema(conn)
    conn.execute("DELETE FROM transcripts")

    indexed = 0
    for path in download_dir.glob("**/*.txt"):
        if path.name.endswith(".meta.json"):
            continue
        ep = _episode_from_name(path.name)
        if ep is None:
            m = EPISODE_FILE_RE.search(path.name)
            if m:
                ep = int(m.group(1))
        if ep is None:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        title = f"Episode {ep}"
        meta_path = next(download_dir.glob(f"**/sn-{ep:04d}.meta.json"), None)
        if meta_path is None:
            meta_path = download_dir / f"sn-{ep:04d}.meta.json"
        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                title = meta.get("title") or title
            except json.JSONDecodeError:
                pass
        conn.execute(
            "INSERT INTO transcripts (episode, title, content) VALUES (?, ?, ?)",
            (ep, title, content),
        )
        indexed += 1

    conn.commit()
    conn.close()

    state = {"indexed_at": time.time(), "documents": indexed, "db": str(db_file)}
    (download_dir / INDEX_STATE_FILE).write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state


def search_index_status(download_dir: Path) -> dict[str, Any]:
    path = download_dir / INDEX_STATE_FILE
    if not path.is_file():
        return {"indexed_at": None, "documents": 0}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"indexed_at": None, "documents": 0}


def _escape_fts_query(query: str) -> str:
    cleaned = re.sub(r'[^\w\s\-"]', " ", query, flags=re.UNICODE)
    parts = [p for p in cleaned.split() if p]
    if not parts:
        return ""
    return " ".join(f'"{p}"' if " " in p else p for p in parts)


def search_transcripts(
    download_dir: Path,
    query: str,
    *,
    db_path: Path | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    download_dir = Path(download_dir)
    db_file = _db_path(download_dir, db_path)
    if not db_file.is_file():
        return []

    fts_q = _escape_fts_query(query)
    if not fts_q:
        return []

    conn = _connect(db_file)
    try:
        rows = conn.execute(
            """
            SELECT episode, title,
                   snippet(transcripts, 2, '<mark>', '</mark>', '…', 48) AS snippet,
                   bm25(transcripts) AS rank
            FROM transcripts
            WHERE transcripts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_q, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    conn.close()

    return [
        {
            "episode": int(row["episode"]),
            "title": row["title"],
            "snippet": row["snippet"],
            "rank": row["rank"],
        }
        for row in rows
    ]
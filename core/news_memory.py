import os
import sqlite3
import time
from typing import Iterable, Set

from core.config import NEWS_MEMORY_DB


def _ensure_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS used_news (
            title_norm TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            source TEXT,
            used_at INTEGER NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_used_at ON used_news(used_at)")


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(NEWS_MEMORY_DB), exist_ok=True)
    conn = sqlite3.connect(NEWS_MEMORY_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    _ensure_db(conn)
    return conn


def normalize_title(title: str) -> str:
    return " ".join(title.lower().split()) if title else ""


def get_used_title_set(ttl_seconds: int) -> Set[str]:
    cutoff = int(time.time()) - ttl_seconds
    with _connect() as conn:
        rows = conn.execute(
            "SELECT title_norm FROM used_news WHERE used_at >= ?",
            (cutoff,),
        ).fetchall()
    return {r[0] for r in rows}


def mark_used_titles(titles: Iterable[str], source: str = None) -> None:
    now = int(time.time())
    rows = []
    for t in titles:
        if not t:
            continue
        title = t.strip()
        if not title:
            continue
        rows.append((normalize_title(title), title, source, now))
    if not rows:
        return
    with _connect() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO used_news (title_norm, title, source, used_at) VALUES (?, ?, ?, ?)",
            rows,
        )


def prune_expired(ttl_seconds: int) -> None:
    cutoff = int(time.time()) - ttl_seconds
    with _connect() as conn:
        conn.execute("DELETE FROM used_news WHERE used_at < ?", (cutoff,))

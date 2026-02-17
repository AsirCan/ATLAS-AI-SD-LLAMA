import json
import os
import sqlite3
import time
from typing import Dict, Iterable, Optional, Set

from core.runtime.config import (
    NEWS_MEMORY_BACKEND,
    NEWS_MEMORY_DB,
    NEWS_MEMORY_JSON,
    NEWS_MEMORY_MONGO_COLLECTION,
    NEWS_MEMORY_MONGO_DB,
    NEWS_MEMORY_MONGO_URI,
)

_MONGO_COLLECTION = None
_SUPPORTED_BACKENDS = {"sqlite", "json", "mongodb", "mongo"}


def _backend() -> str:
    selected = (NEWS_MEMORY_BACKEND or "sqlite").strip().lower()
    if selected not in _SUPPORTED_BACKENDS:
        return "sqlite"
    return "mongodb" if selected == "mongo" else selected


def _safe_mkdir_for_file(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _normalize_row(title_norm: str, title: str, source: Optional[str], used_at: int) -> Dict[str, object]:
    return {
        "title_norm": title_norm,
        "title": title,
        "source": source,
        "used_at": used_at,
    }


def _build_rows(titles: Iterable[str], source: str = None) -> Dict[str, Dict[str, object]]:
    now = int(time.time())
    rows: Dict[str, Dict[str, object]] = {}
    for t in titles:
        if not t:
            continue
        title = str(t).strip()
        if not title:
            continue
        title_norm = normalize_title(title)
        if not title_norm:
            continue
        rows[title_norm] = _normalize_row(title_norm, title, source, now)
    return rows


# ------------------------------
# SQLite backend
# ------------------------------
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
    _safe_mkdir_for_file(NEWS_MEMORY_DB)
    conn = sqlite3.connect(NEWS_MEMORY_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    _ensure_db(conn)
    return conn


# ------------------------------
# JSON backend
# ------------------------------
def _json_read_rows() -> Dict[str, Dict[str, object]]:
    if not os.path.exists(NEWS_MEMORY_JSON):
        return {}

    try:
        with open(NEWS_MEMORY_JSON, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}

    raw_rows = payload.get("used_news", []) if isinstance(payload, dict) else []
    if not isinstance(raw_rows, list):
        return {}

    rows: Dict[str, Dict[str, object]] = {}
    for item in raw_rows:
        if not isinstance(item, dict):
            continue
        title_norm = str(item.get("title_norm", "")).strip()
        if not title_norm:
            continue
        title = str(item.get("title", "")).strip() or title_norm
        source = item.get("source")
        if source is not None:
            source = str(source)
        try:
            used_at = int(item.get("used_at", 0))
        except (TypeError, ValueError):
            continue
        rows[title_norm] = _normalize_row(title_norm, title, source, used_at)
    return rows


def _json_write_rows(rows: Dict[str, Dict[str, object]]) -> None:
    _safe_mkdir_for_file(NEWS_MEMORY_JSON)
    payload = {
        "used_news": sorted(rows.values(), key=lambda x: int(x["used_at"]), reverse=True)
    }
    with open(NEWS_MEMORY_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


# ------------------------------
# MongoDB backend
# ------------------------------
def _mongo_collection():
    global _MONGO_COLLECTION
    if _MONGO_COLLECTION is not None:
        return _MONGO_COLLECTION

    try:
        from pymongo import MongoClient
    except ImportError as exc:
        raise RuntimeError(
            "MongoDB backend selected but pymongo is not installed. Install it with: pip install pymongo"
        ) from exc

    client = MongoClient(NEWS_MEMORY_MONGO_URI, serverSelectionTimeoutMS=3000)
    collection = client[NEWS_MEMORY_MONGO_DB][NEWS_MEMORY_MONGO_COLLECTION]
    collection.create_index("title_norm", unique=True)
    collection.create_index("used_at")
    _MONGO_COLLECTION = collection
    return _MONGO_COLLECTION


def normalize_title(title: str) -> str:
    return " ".join(title.lower().split()) if title else ""


def get_used_title_set(ttl_seconds: int) -> Set[str]:
    cutoff = int(time.time()) - ttl_seconds
    backend = _backend()

    if backend == "sqlite":
        with _connect() as conn:
            rows = conn.execute(
                "SELECT title_norm FROM used_news WHERE used_at >= ?",
                (cutoff,),
            ).fetchall()
        return {r[0] for r in rows}

    if backend == "json":
        rows = _json_read_rows()
        return {
            key
            for key, row in rows.items()
            if int(row.get("used_at", 0)) >= cutoff
        }

    collection = _mongo_collection()
    docs = collection.find(
        {"used_at": {"$gte": cutoff}},
        {"_id": 0, "title_norm": 1},
    )
    return {
        str(doc.get("title_norm", "")).strip()
        for doc in docs
        if str(doc.get("title_norm", "")).strip()
    }


def mark_used_titles(titles: Iterable[str], source: str = None) -> None:
    rows = _build_rows(titles, source=source)
    if not rows:
        return

    backend = _backend()

    if backend == "sqlite":
        sql_rows = [
            (row["title_norm"], row["title"], row["source"], row["used_at"])
            for row in rows.values()
        ]
        with _connect() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO used_news (title_norm, title, source, used_at) VALUES (?, ?, ?, ?)",
                sql_rows,
            )
        return

    if backend == "json":
        existing = _json_read_rows()
        existing.update(rows)
        _json_write_rows(existing)
        return

    collection = _mongo_collection()
    for row in rows.values():
        collection.update_one(
            {"title_norm": row["title_norm"]},
            {"$set": row},
            upsert=True,
        )


def prune_expired(ttl_seconds: int) -> None:
    cutoff = int(time.time()) - ttl_seconds
    backend = _backend()

    if backend == "sqlite":
        with _connect() as conn:
            conn.execute("DELETE FROM used_news WHERE used_at < ?", (cutoff,))
        return

    if backend == "json":
        rows = _json_read_rows()
        pruned = {
            key: row for key, row in rows.items() if int(row.get("used_at", 0)) >= cutoff
        }
        _json_write_rows(pruned)
        return

    collection = _mongo_collection()
    collection.delete_many({"used_at": {"$lt": cutoff}})

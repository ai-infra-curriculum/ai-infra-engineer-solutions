"""SQLite-backed manifest of replicated objects."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class ObjectRecord:
    key: str
    src_etag: str
    src_size: int
    dst_etag: str
    sha256: str
    last_synced_at: float


class Manifest:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._init()

    def _init(self) -> None:
        with self._conn() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS objects (
                    key TEXT PRIMARY KEY,
                    src_etag TEXT NOT NULL,
                    src_size INTEGER NOT NULL,
                    dst_etag TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    last_synced_at REAL NOT NULL
                )
                """,
            )

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def upsert(self, rec: ObjectRecord) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO objects VALUES (?,?,?,?,?,?)",
                (rec.key, rec.src_etag, rec.src_size, rec.dst_etag, rec.sha256, rec.last_synced_at),
            )

    def get(self, key: str) -> ObjectRecord | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT key, src_etag, src_size, dst_etag, sha256, last_synced_at FROM objects WHERE key = ?",
                (key,),
            ).fetchone()
            return ObjectRecord(*row) if row else None

    def all_keys(self) -> set[str]:
        with self._conn() as c:
            return {r[0] for r in c.execute("SELECT key FROM objects")}

    def delete(self, key: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM objects WHERE key = ?", (key,))

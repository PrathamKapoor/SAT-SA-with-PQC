"""Database engine abstraction.

The platform's durable state (identities, permissions, audit mirror rows,
migration bookkeeping) is reached only through the :class:`DatabaseEngine`
interface. Phase 1 implements SQLite; the interface is intentionally thin so
a quantum-safe channel, encrypted storage, or a managed database can replace
the local SQLite file in a later phase without touching repositories or
services — the production database requirements (encrypted at rest,
cryptographic identity columns, immutable audit) are satisfied then.

URL form: ``sqlite:///<file-path>``. The path may be absolute.
"""
from __future__ import annotations

import sqlite3
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Sequence

from qsmlops.core.errors import DuplicateEntryError, StorageError


def parse_database_url(url: str) -> tuple[str, Path]:
    """Split a database URL into (dialect, path)."""
    if url.startswith("sqlite:///"):
        return "sqlite", Path(url[len("sqlite:///") :])
    raise StorageError(
        f"unsupported database URL {url!r}; expected sqlite:///<file>"
    )


class DatabaseEngine(ABC):
    """Minimal statement-level engine surface."""

    @property
    @abstractmethod
    def dialect(self) -> str: ...

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        """Execute a write statement and commit."""

    @abstractmethod
    def query_one(self, sql: str, params: Sequence[Any] = ()) -> dict | None: ...

    @abstractmethod
    def query_all(self, sql: str, params: Sequence[Any] = ()) -> list[dict]: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def transaction(self):
        """Context manager: statements executed via ``execute()`` inside the
        block either all commit together or none do (Phase 2 — see
        docs/phase2/evidence-persistence.md). Prior to this, every
        ``execute()`` call committed independently; single-statement callers
        are unaffected, this only changes behaviour for callers that opt in
        by using ``with engine.transaction():``."""


class SQLiteDatabaseEngine(DatabaseEngine):
    """SQLite implementation with serialized writes (single writer lock) and
    row-factory dict results. Errors are translated into platform errors."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None
        # Phase 2: RLock (was Lock) so transaction() can hold the lock across
        # a whole multi-statement block while still calling the public
        # execute()/query_one()/query_all() methods (which each also acquire
        # this lock) from inside that block on the same thread, without
        # deadlocking. Single-caller-at-a-time semantics are unchanged for
        # every existing call site — this only newly permits the *same*
        # thread to re-enter, which none of them do outside transaction().
        self._lock = threading.RLock()
        self._in_transaction = False

    @property
    def dialect(self) -> str:
        return "sqlite"

    def connect(self) -> None:
        with self._lock:
            if self._conn is not None:
                return
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(
                str(self.db_path), check_same_thread=False, isolation_level=None
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._conn = conn

    @property
    def _connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self.connect()
            assert self._conn is not None
        return self._conn

    def _translate(self, exc: sqlite3.Error, sql: str) -> Exception:
        if isinstance(exc, sqlite3.IntegrityError) and "UNIQUE" in str(exc).upper():
            return DuplicateEntryError(f"duplicate entry: {exc}")
        return StorageError(f"database error while executing {sql!r}: {exc}")

    def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        with self._lock:
            try:
                self._connection.execute(sql, tuple(params))
            except sqlite3.Error as exc:
                raise self._translate(exc, sql) from exc

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> dict | None:
        row = self._connection.execute(sql, tuple(params)).fetchone()
        return dict(row) if row is not None else None

    def query_all(self, sql: str, params: Sequence[Any] = ()) -> list[dict]:
        rows = self._connection.execute(sql, tuple(params)).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    @contextmanager
    def transaction(self):
        self.connect()  # ensure connected *before* taking the lock, so a
                         # lazy connect never needs to reacquire it
        with self._lock:
            if self._in_transaction:
                # Nested `with transaction():` on the same thread: join the
                # outer transaction rather than issuing a second BEGIN
                # (which sqlite3 would reject).
                yield self
                return
            try:
                self._conn.execute("BEGIN IMMEDIATE")
            except sqlite3.Error as exc:
                raise self._translate(exc, "BEGIN IMMEDIATE") from exc
            self._in_transaction = True
            try:
                yield self
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            else:
                self._conn.execute("COMMIT")
            finally:
                self._in_transaction = False


def create_engine(url: str) -> DatabaseEngine:
    dialect, path = parse_database_url(url)
    if dialect == "sqlite":
        return SQLiteDatabaseEngine(path)
    raise StorageError(f"no engine implementation for dialect {dialect!r}")

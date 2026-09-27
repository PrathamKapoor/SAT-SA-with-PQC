"""Pooled PostgreSQL implementation of the existing statement-level engine."""

from __future__ import annotations

import threading
from collections.abc import Sequence
from contextlib import contextmanager
from typing import Any

from psycopg import Error as PsycopgError
from psycopg import errors, rows
from psycopg.conninfo import conninfo_to_dict
from psycopg_pool import ConnectionPool

from qsmlops.core.errors import DuplicateEntryError, StorageError
from qsmlops.database.engine import DatabaseEngine


def _bind_qmarks(statement: str) -> str:
    """Translate repository value binds, preserving SQL literals/comments.

    Repositories use SQLite's qmark convention. Only SQL syntax is translated;
    parameter values are always passed separately to psycopg.
    """
    output: list[str] = []
    i = 0
    state = "code"
    dollar_tag = ""
    while i < len(statement):
        char = statement[i]
        next_char = statement[i + 1] if i + 1 < len(statement) else ""
        if state == "code":
            if char == "'":
                state = "single"
            elif char == '"':
                state = "double"
            elif char == "-" and next_char == "-":
                state = "line_comment"
                output.append("--")
                i += 2
                continue
            elif char == "/" and next_char == "*":
                state = "block_comment"
                output.append("/*")
                i += 2
                continue
            elif char == "$":
                end = statement.find("$", i + 1)
                if end != -1 and all(
                    c.isalnum() or c == "_" for c in statement[i + 1 : end]
                ):
                    dollar_tag = statement[i : end + 1]
                    state = "dollar"
                    output.append(dollar_tag)
                    i = end + 1
                    continue
            elif char == "?":
                output.append("%s")
                i += 1
                continue
        elif state == "single" and char == "'":
            if next_char == "'":
                output.append("''")
                i += 2
                continue
            state = "code"
        elif state == "double" and char == '"':
            if next_char == '"':
                output.append('""')
                i += 2
                continue
            state = "code"
        elif state == "line_comment" and char == "\n":
            state = "code"
        elif state == "block_comment" and char == "*" and next_char == "/":
            state = "code"
            output.append("*/")
            i += 2
            continue
        elif state == "dollar" and statement.startswith(dollar_tag, i):
            state = "code"
            output.append(dollar_tag)
            i += len(dollar_tag)
            continue
        output.append(char)
        i += 1
    return "".join(output)


class PostgresDatabaseEngine(DatabaseEngine):
    """Connection pool with one thread-local connection per transaction."""

    def __init__(
        self,
        dsn: str,
        *,
        min_size: int = 1,
        max_size: int = 5,
        connect_timeout: int = 5,
        pool_timeout: int = 5,
        statement_timeout_ms: int = 60_000,
    ) -> None:
        if min_size < 0 or max_size < 1 or min_size > max_size:
            raise ValueError("invalid PostgreSQL connection pool bounds")
        if connect_timeout < 1 or pool_timeout < 1 or statement_timeout_ms < 1:
            raise ValueError("PostgreSQL timeouts must be positive")
        self.dsn = dsn
        # Keep any server options already in the DSN (e.g. search_path):
        # a connection keyword argument replaces, not extends, the DSN value.
        dsn_options = conninfo_to_dict(dsn).get("options") or ""
        options = f"{dsn_options} -c statement_timeout={statement_timeout_ms}".strip()
        self._pool = ConnectionPool(
            conninfo=dsn,
            min_size=min_size,
            max_size=max_size,
            timeout=pool_timeout,
            kwargs={
                "row_factory": rows.dict_row,
                "connect_timeout": connect_timeout,
                "options": options,
            },
            open=False,
        )
        self._local = threading.local()
        self._lock = threading.Lock()
        self._opened = False

    @property
    def dialect(self) -> str:
        return "postgresql"

    def connect(self) -> None:
        with self._lock:
            if not self._opened:
                try:
                    self._pool.open(wait=True)
                except (PsycopgError, TimeoutError) as exc:
                    raise StorageError(f"PostgreSQL connection failed: {exc}") from exc
                self._opened = True

    @staticmethod
    def _translate(exc: PsycopgError, sql: str) -> Exception:
        if isinstance(exc, errors.UniqueViolation):
            return DuplicateEntryError(f"duplicate entry: {exc}")
        return StorageError(f"database error while executing {sql!r}: {exc}")

    @contextmanager
    def _connection(self):
        self.connect()
        pinned = getattr(self._local, "connection", None)
        if pinned is not None:
            yield pinned
        else:
            with self._pool.connection() as connection:
                yield connection

    def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        try:
            with self._connection() as connection:
                connection.execute(_bind_qmarks(sql), tuple(params))
        except PsycopgError as exc:
            raise self._translate(exc, sql) from exc

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> dict | None:
        try:
            with self._connection() as connection:
                return connection.execute(_bind_qmarks(sql), tuple(params)).fetchone()
        except PsycopgError as exc:
            raise self._translate(exc, sql) from exc

    def query_all(self, sql: str, params: Sequence[Any] = ()) -> list[dict]:
        try:
            with self._connection() as connection:
                return connection.execute(_bind_qmarks(sql), tuple(params)).fetchall()
        except PsycopgError as exc:
            raise self._translate(exc, sql) from exc

    @contextmanager
    def transaction(self):
        self.connect()
        if getattr(self._local, "connection", None) is not None:
            yield self
            return
        with self._pool.connection() as connection:
            self._local.connection = connection
            try:
                yield self
            finally:
                del self._local.connection

    def close(self) -> None:
        with self._lock:
            if self._opened:
                self._pool.close()
                self._opened = False

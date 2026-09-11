"""Database ingestion adapter.

The audit identified the missing DB ingestion path. Submission
data often already exists inside an upstream CSE SQLite database
(SIEM extract, compliance export, etc.). The DB adapter reads
records from an external SQLite database and converts each row
into the same RawRow shape the CSV/JSON readers emit, so the
rest of the ingestion pipeline (canonical normalization,
SourceRecord persistence) treats database-derived records
identically to file-derived records.

This adapter is read-only with respect to the source DB — it
opens the file in read-only mode via SQLite URI and never writes
back. The source DB's rows are converted to canonical RawRow
records with the same ``file_digest`` semantics: the digest
covers the canonicalized raw row bytes, not the original
database page, so the source-of-truth stays at the row level
(not the storage level).
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from qsmlops.crypto.hashing import digest_document, sha3_hex
from satsa.ingest.readers import IngestionFormatError, ParsedFile, RawRow


def _canonical_raw(data: dict) -> str:
    return digest_document({k: ("" if v is None else str(v)) for k, v in data.items()})


def _row_to_data(row: tuple, columns: list[str]) -> dict:
    out = {}
    for col, val in zip(columns, row):
        out[col] = val
    return out


def read_sqlite_table(source_db: Path, table: str, *,
                      where: str = "") -> ParsedFile:
    """Read one table from an external SQLite database and return a
    ParsedFile with the same shape the CSV/JSON readers produce.

    The ``file_digest`` is the SHA3-256 of the concatenation of all
    rows' canonical JSON — it identifies the *snapshot* of the
    source rows we read, not the SQLite file itself. Each row's
    ``original_digest`` is the canonical digest of that row's
    contents, identical to what the CSV/JSON readers compute.
    """
    if not Path(source_db).is_file():
        raise IngestionFormatError(f"source DB not found: {source_db}")
    try:
        # read-only URI mode prevents accidental writes to the
        # upstream database
        uri = f"file:{Path(source_db).as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        raise IngestionFormatError(
            f"could not open source DB {source_db}: {exc}") from exc
    try:
        cur = conn.cursor()
        # Inspect the table to discover its column names.
        try:
            info = cur.execute(
                f"PRAGMA table_info({table})").fetchall()
        except sqlite3.Error as exc:
            raise IngestionFormatError(
                f"could not read table {table!r}: {exc}") from exc
        if not info:
            raise IngestionFormatError(
                f"table {table!r} not found in {source_db}")
        columns = [row[1] for row in info]  # PRAGMA table_info row 1 = name
        sql = f"SELECT {', '.join(columns)} FROM {table}"
        if where:
            sql += " WHERE " + where
        try:
            rows = cur.execute(sql).fetchall()
        except sqlite3.Error as exc:
            raise IngestionFormatError(
                f"could not read rows from {table!r}: {exc}") from exc
        canonical_bytes = []
        parsed_rows = []
        for i, row in enumerate(rows, start=1):
            data = _row_to_data(row, columns)
            parsed_rows.append(RawRow(
                row_number=i, data=data,
                original_digest=_canonical_raw(data),
                source_fmt="sqlite",
                locator=f"row {i}",
            ))
            canonical_bytes.append(_canonical_raw(data))
        snapshot_bytes = "\n".join(canonical_bytes).encode("utf-8")
        file_digest = sha3_hex(snapshot_bytes)
        return ParsedFile(
            category=table, format="sqlite",
            file_digest=file_digest, rows=parsed_rows,
        )
    finally:
        conn.close()


def read_sqlite_categories(source_db: Path,
                            categories: dict) -> dict:
    """Read several categories from the source DB. ``categories``
    is a dict of ``{category: (table_name, where_clause)}``. Each
    category returns a ParsedFile; the caller threads them through
    ``IngestionService.submit_files`` like any other format.
    """
    out = {}
    for category, spec in categories.items():
        if isinstance(spec, str):
            table, where = spec, ""
        else:
            table, where = spec
        out[category] = read_sqlite_table(source_db, table, where=where)
    return out
"""Parsing of submission files into raw rows with source provenance.

Supported formats: CSV and JSON (array-of-objects, or JSONL). Each parsed
row carries a SourceRecord-shaped pointer (file digest, format, locator,
per-row digest) so every accepted domain record can later be traced back to
the exact submitted bytes it came from (SIH-EX explainability chain).

No network access, database writes or third-party parsers happen here —
stdlib csv/json only, which keeps ingestion deterministic and air-gapped.
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from qsmlops.crypto.hashing import digest_document, sha3_hex

MAX_FILE_BYTES = 512 * 1024 * 1024  # 512 MiB hard cap per submission file


class IngestionFormatError(Exception):
    """A submission file could not be parsed at all (bad bytes, bad CSV,
    bad JSON). Distinct from row-level rejection: this fails the file."""


@dataclass
class RawRow:
    """One parsed row plus its source pointer."""
    row_number: int            # 1-based data row (header excluded) / array index+1
    data: dict                 # raw column name -> raw value (strings)
    original_digest: str       # sha3 of the canonicalized raw row
    source_fmt: str            # "csv" | "json"
    locator: str               # e.g. "row 12" (CSV) or "index 12" (JSON)


@dataclass
class ParsedFile:
    category: str
    format: str
    file_digest: str           # sha3 of the exact bytes
    rows: list = field(default_factory=list)   # list[RawRow]


def _canonical_raw(data: dict) -> str:
    return digest_document({k: ("" if v is None else str(v)) for k, v in data.items()})


def read_file_bytes(path: Path) -> bytes:
    p = Path(path)
    if not p.is_file():
        raise IngestionFormatError(f"file not found: {p}")
    size = p.stat().st_size
    if size > MAX_FILE_BYTES:
        raise IngestionFormatError(
            f"file {p.name} is {size} bytes; limit is {MAX_FILE_BYTES}")
    return p.read_bytes()


def parse_csv_bytes(raw: bytes, category: str) -> ParsedFile:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise IngestionFormatError(f"{category}: not valid UTF-8 ({exc})") from exc
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or not any((f or "").strip() for f in reader.fieldnames):
        raise IngestionFormatError(f"{category}: CSV has no header row")
    rows: list[RawRow] = []
    for i, rec in enumerate(reader, start=1):
        if rec is None:
            continue
        data = {k: (v if v is not None else "") for k, v in rec.items()
                if k is not None}
        if not any(str(v).strip() for v in data.values()):
            continue  # skip fully blank lines; not a record, not an error
        rows.append(RawRow(row_number=i, data=data,
                           original_digest=_canonical_raw(data),
                           source_fmt="csv", locator=f"row {i}"))
    return ParsedFile(category=category, format="csv",
                      file_digest=sha3_hex(raw), rows=rows)


def _rows_from_json_obj(obj, category: str) -> list:
    if isinstance(obj, dict):
        # tolerate a wrapping key: {"alerts": [...]} etc.
        for key in (category, "records", "rows", "items", "data"):
            if isinstance(obj.get(key), list):
                return obj[key]
        raise IngestionFormatError(
            f"{category}: JSON object must be an array of records, or contain one under "
            f"'{category}'/'records'/'rows'/'items'/'data'")
    if isinstance(obj, list):
        return obj
    raise IngestionFormatError(f"{category}: top-level JSON must be an array")


def parse_json_bytes(raw: bytes, category: str, *,
                     force_jsonl: bool = False) -> ParsedFile:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise IngestionFormatError(f"{category}: not valid UTF-8 ({exc}") from exc
    stripped = text.strip()
    rows: list[RawRow] = []
    if force_jsonl or not (stripped.startswith("[") or stripped.startswith("{")):
        # JSONL: one object per line
        for i, line in enumerate(stripped.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise IngestionFormatError(
                    f"{category}: invalid JSONL at line {i} ({exc})") from exc
            if not isinstance(item, dict):
                raise IngestionFormatError(
                    f"{category}: JSONL line {i} is not an object")
            data = {str(k): ("" if v is None else v) for k, v in item.items()}
            rows.append(RawRow(row_number=i, data=data,
                               original_digest=_canonical_raw(data),
                               source_fmt="json", locator=f"line {i}"))
    else:
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise IngestionFormatError(f"{category}: invalid JSON ({exc})") from exc
        items = _rows_from_json_obj(obj, category)
        for i, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                raise IngestionFormatError(
                    f"{category}: record {i} is not a JSON object")
            data = {str(k): ("" if v is None else v) for k, v in item.items()}
            rows.append(RawRow(row_number=i, data=data,
                               original_digest=_canonical_raw(data),
                               source_fmt="json", locator=f"index {i}"))
    return ParsedFile(category=category, format="json",
                      file_digest=sha3_hex(raw), rows=rows)


def parse_file(path: Path, category: str) -> ParsedFile:
    raw = read_file_bytes(path)
    suffix = Path(path).suffix.lower()
    if suffix == ".csv":
        return parse_csv_bytes(raw, category)
    if suffix == ".json":
        return parse_json_bytes(raw, category)
    if suffix in (".jsonl", ".ndjson"):
        return parse_json_bytes(raw, category, force_jsonl=True)
    raise IngestionFormatError(
        f"{Path(path).name}: unsupported extension {suffix!r} (expected .csv/.json/.jsonl)")


def scan_directory(directory: Path) -> dict:
    """Find recognized submission files in a directory.

    Returns {category: Path}. Recognized names: <category>.csv/.json/.jsonl
    (also the singular for the plural categories, e.g. 'alerts.csv' and
    'alert.csv'). Unknown files are ignored by ingestion but surfaced in the
    report by the caller."""
    directory = Path(directory)
    found: dict = {}
    if not directory.is_dir():
        raise IngestionFormatError(f"submission directory not found: {directory}")
    aliases = {
        "alerts": ("alerts", "alert"),
        "cases": ("cases", "case"),
        "investigation_steps": ("investigation_steps", "investigation", "investigations"),
        "escalations": ("escalations", "escalation"),
        "dispositions": ("dispositions", "disposition", "closure", "closures"),
        "assets": ("assets", "asset", "inventory"),
    }
    for child in sorted(directory.iterdir()):
        if not child.is_file():
            continue
        stem = child.stem.lower()
        for category, names in aliases.items():
            if stem in names and child.suffix.lower() in (".csv", ".json", ".jsonl", ".ndjson"):
                found.setdefault(category, child)
    return found

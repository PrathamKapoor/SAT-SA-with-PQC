"""Bounded disk-backed parsing for hosted submission artifacts.

The existing SAT-SA RawRow and normalizer contracts remain authoritative.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import ijson

from satsa.ingest.readers import IngestionFormatError, ParsedFile, RawRow, _canonical_raw
from satsa.ingest.spec import CATEGORY_FIELDS
from satsa.submissions.storage import file_sha3_256


def parse_streamed_file(path: Path, category: str, *, max_rows: int = 100_000) -> ParsedFile:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in {".csv", ".json", ".jsonl", ".ndjson"}:
        raise IngestionFormatError(f"{category}: unsupported format")
    parsed = ParsedFile(category=category, format="csv" if suffix == ".csv" else "json",
                        file_digest=file_sha3_256(path))
    required = [field for field in CATEGORY_FIELDS[category] if field.required]

    def check_schema(keys) -> None:
        normalized = {str(key).strip().lower().replace(" ", "_").replace("-", "_")
                      for key in keys}
        missing = [field.name for field in required if not normalized.intersection(
            name.lower() for name in field.all_names())]
        if missing:
            raise IngestionFormatError(
                f"{category}: missing required columns/fields {', '.join(missing)}")

    def add(item: dict, index: int, locator: str) -> None:
        if not isinstance(item, dict):
            raise IngestionFormatError(f"{category}: {locator} is not an object")
        if len(parsed.rows) >= max_rows:
            raise IngestionFormatError(f"{category}: record limit {max_rows} exceeded")
        if not parsed.rows:
            check_schema(item.keys())
        data = {str(k): "" if v is None else v for k, v in item.items()}
        parsed.rows.append(RawRow(index, data, _canonical_raw(data), parsed.format, locator))

    try:
        if suffix == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as source:
                reader = csv.DictReader(source, strict=True)
                if not reader.fieldnames or not any((f or "").strip() for f in reader.fieldnames):
                    raise IngestionFormatError(f"{category}: CSV has no header row")
                check_schema(reader.fieldnames)
                for index, row in enumerate(reader, 1):
                    if None in row:
                        raise IngestionFormatError(f"{category}: row {index} has extra columns")
                    data = {key: value if value is not None else "" for key, value in row.items()}
                    if any(str(value).strip() for value in data.values()):
                        add(data, index, f"row {index}")
        elif suffix in {".jsonl", ".ndjson"}:
            with path.open("r", encoding="utf-8-sig") as source:
                for index, line in enumerate(source, 1):
                    if line.strip():
                        add(json.loads(line), index, f"line {index}")
        else:
            with path.open("rb") as source:
                prefix = None
                for event_prefix, event, _ in ijson.parse(source):
                    if event == "start_array" and event_prefix in {
                        "", category, "records", "rows", "items", "data"
                    }:
                        prefix = (event_prefix + ".item") if event_prefix else "item"
                        break
                if prefix is None:
                    raise IngestionFormatError(f"{category}: JSON record array missing")
            with path.open("rb") as source:
                for index, item in enumerate(ijson.items(source, prefix, use_float=True), 1):
                    add(item, index, f"index {index}")
    except (UnicodeError, csv.Error, json.JSONDecodeError, ijson.JSONError, ValueError) as exc:
        raise IngestionFormatError(f"{category}: malformed {suffix[1:]} ({exc})") from exc
    return parsed

"""Expert-label ingestion, validation and adjudication (schema v1).

Ready for a future, legitimate labelling study. No expert labels exist in
this repository; ``docs/demo/expert-labels.sample.json`` is a template and
is refused here (``label_source`` must not be a template).

One JSON Lines record per annotation::

    {"schema": "satsa-expert-label/1",
     "label_source": "study-2026-a",          # study or batch identifier
     "annotator_id": "ann-07",                # pseudonym; no names/e-mails
     "labelled_at": "2026-10-01T10:15:00Z",   # UTC ISO-8601
     "target_type": "finding",                # finding | case | scenario
     "target_id": "finding_ab12...",
     "label": "true_issue",                   # see LABELS
     "confidence": 0.8,                        # optional, 0..1
     "rationale": "free text, optional",
     "case_set_digest": "sha256 of the frozen case set"}

Adjudication records use ``"schema": "satsa-expert-adjudication/1"`` with
``target_type``, ``target_id``, ``label``, ``adjudicator_id`` and
``adjudicated_at``; they override the majority for that target.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from itertools import combinations
from pathlib import Path
from typing import Any

LABEL_SCHEMA = "satsa-expert-label/1"
ADJUDICATION_SCHEMA = "satsa-expert-adjudication/1"
LABELS = ("true_issue", "not_issue", "insufficient_evidence")
TARGET_TYPES = ("finding", "case", "scenario")
_PSEUDONYM = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$")
_TEMPLATE_SOURCES = {"sample-template", "template", "example"}


def _utc(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return True


def validate_label(record: dict[str, Any]) -> list[str]:
    errors = []
    if record.get("schema") != LABEL_SCHEMA:
        errors.append(f"schema must be {LABEL_SCHEMA}")
    source = str(record.get("label_source") or "")
    if not source:
        errors.append("label_source is required")
    elif source.lower() in _TEMPLATE_SOURCES:
        errors.append("template labels are not expert labels")
    annotator = str(record.get("annotator_id") or "")
    if not _PSEUDONYM.fullmatch(annotator):
        errors.append("annotator_id must be a pseudonym (letters, digits, - or _)")
    if not _utc(record.get("labelled_at")):
        errors.append("labelled_at must be UTC ISO-8601 ending in Z")
    if record.get("target_type") not in TARGET_TYPES:
        errors.append(f"target_type must be one of {TARGET_TYPES}")
    if not record.get("target_id"):
        errors.append("target_id is required")
    if record.get("label") not in LABELS:
        errors.append(f"label must be one of {LABELS}")
    confidence = record.get("confidence")
    if confidence is not None and not (
        isinstance(confidence, (int, float)) and 0 <= confidence <= 1
    ):
        errors.append("confidence must be between 0 and 1")
    if not record.get("case_set_digest"):
        errors.append("case_set_digest is required")
    return errors


def load_labels(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (accepted records, rejections with line numbers and reasons)."""
    accepted, rejected = [], []
    seen: set[tuple[str, str, str]] = set()
    for line_number, line in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            rejected.append({"line": line_number, "reasons": [f"invalid JSON: {exc}"]})
            continue
        if record.get("schema") == ADJUDICATION_SCHEMA:
            accepted.append(record)
            continue
        errors = validate_label(record)
        key = (
            str(record.get("annotator_id")),
            str(record.get("target_type")),
            str(record.get("target_id")),
        )
        if not errors and key in seen:
            errors.append("duplicate annotation by the same annotator")
        if errors:
            rejected.append({"line": line_number, "reasons": errors})
            continue
        seen.add(key)
        accepted.append(record)
    return accepted, rejected


def cohen_kappa(first: list[str], second: list[str]) -> float | None:
    if len(first) != len(second) or not first:
        return None
    n = len(first)
    observed = sum(a == b for a, b in zip(first, second)) / n
    counts_a, counts_b = Counter(first), Counter(second)
    expected = sum(counts_a[c] * counts_b[c] for c in LABELS) / (n * n)
    return None if expected == 1 else (observed - expected) / (1 - expected)


def adjudicate(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Majority label per target, overridden by explicit adjudication.

    Targets without a majority and without adjudication are ``unresolved``;
    they are never silently assigned a label.
    """
    by_target: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    adjudications = {}
    for record in records:
        key = (record["target_type"], record["target_id"])
        if record.get("schema") == ADJUDICATION_SCHEMA:
            adjudications[key] = record
        else:
            by_target[key].append(record)
    consensus = {}
    for key, marks in sorted(by_target.items()):
        counts = Counter(a["label"] for a in marks)
        top = counts.most_common()
        majority = top[0][0] if len(top) == 1 or top[0][1] > top[1][1] else None
        if key in adjudications:
            label, method = adjudications[key]["label"], "adjudicated"
        elif majority is not None:
            label, method = majority, "majority"
        else:
            label, method = None, "unresolved"
        consensus[f"{key[0]}:{key[1]}"] = {
            "label": label,
            "method": method,
            "annotations": len(marks),
            "label_counts": dict(counts),
        }
    annotators = sorted({a["annotator_id"] for v in by_target.values() for a in v})
    pairwise = {}
    for first, second in combinations(annotators, 2):
        shared = [
            (
                next(a["label"] for a in v if a["annotator_id"] == first),
                next(a["label"] for a in v if a["annotator_id"] == second),
            )
            for v in by_target.values()
            if {first, second} <= {a["annotator_id"] for a in v}
        ]
        if shared:
            pairwise[f"{first}|{second}"] = {
                "shared_targets": len(shared),
                "percent_agreement": sum(a == b for a, b in shared) / len(shared),
                "cohen_kappa": cohen_kappa(
                    [a for a, _ in shared], [b for _, b in shared]
                ),
            }
    return {
        "targets": len(consensus),
        "annotators": len(annotators),
        "unresolved": sum(v["method"] == "unresolved" for v in consensus.values()),
        "consensus": consensus,
        "pairwise_agreement": pairwise,
    }

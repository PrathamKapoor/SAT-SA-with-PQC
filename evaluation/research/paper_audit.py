"""Publication audits: numbers, citations and claim wording of the manuscript.

numerical   rebuilding paper data, tables and figures from the freeze
            reproduces the committed files exactly
manuscript  every \\V key is defined; no result-like decimal is typed by hand
citations   every \\cite key is in references.bib; every bib entry is a
            verified row of the literature matrix
claims      no prohibited wording (novelty, superiority, production,
            validation claims the evidence does not support)
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any

from evaluation.research.paper import audit_manuscript, build_paper_data, values_tex

# Wording the evidence does not support. A line mentioning a superseded
# experiment ("supersed", "replaced") may name X02.
PROHIBITED: dict[str, str] = {
    "state-of-the-art": r"state[- ]of[- ]the[- ]art",
    "best": r"\bbest\b",
    "superior": r"\bsuperior\b",
    "first-of-kind": r"\bfirst (system|approach|work|framework|tool) to\b|\bthe first\b",
    "novel": r"\bnovel\b",
    "real-world SOC validation": r"real[- ]world SOC validation",
    "expert validated": r"expert[- ]validated",
    "human study validated": r"human[- ]study[- ]validated",
    "production claim": r"production[- ](scale|ready|validated|grade)",
    "enterprise-scale": r"enterprise[- ]scale",
    "generalizable": r"generali[sz]able",
    "tamper-proof": r"tamper[- ]proof",
    "secure against all attacks": r"secure against all",
    "fully autonomous": r"fully autonomous",
    "fully fault tolerant": r"fully fault[- ]tolerant",
    "cloud-validated": r"cloud[- ]validated",
    "prevented mutations": r"\bprevent(s|ed)?\b",
    "deployed": r"\bdeployed\b",
    "17 workers": r"\b17\b[^.]{0,40}\bworkers?\b",
}
_SUPERSEDED_X02 = re.compile(r"\bX02\b(?!b)")
_CITE = re.compile(r"\\cite[pt]?\*?(?:\[[^\]]*\])*\{([^}]+)\}")
_BIBKEY = re.compile(r"@\w+\{([^,\s]+),")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tex_files(paper_dir: Path) -> list[Path]:
    return [paper_dir / "manuscript.tex", *sorted((paper_dir / "sections").glob("*.tex"))]


def audit_numbers(freeze_dir: Path, paper_dir: Path) -> dict[str, Any]:
    """Regenerate every generated paper file in a scratch copy and compare."""
    from evaluation.research.paper_assets import build_all

    problems: list[str] = []
    data = build_paper_data(freeze_dir, paper_dir / "data" / "claims-spec.json")
    committed = json.loads((paper_dir / "data" / "paper-data.json").read_text("utf-8"))
    if data != committed:
        differing = [
            a["claim_id"]
            for a, b in zip(data["claims"], committed["claims"], strict=False)
            if a != b
        ]
        problems.append(f"paper-data.json differs from rebuild: {differing[:10]}")
    if values_tex(data) != (paper_dir / "data" / "values.tex").read_text("utf-8"):
        problems.append("values.tex differs from rebuild")
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp)
        (scratch / "tables").mkdir()
        (scratch / "figures").mkdir()
        build_all(freeze_dir, scratch)
        for name in ("tables", "figures", "supplementary/generated"):
            fresh = {p.name: _sha(p) for p in (scratch / name).iterdir() if p.is_file()}
            kept_dir = paper_dir / name
            kept = (
                {p.name: _sha(p) for p in kept_dir.iterdir() if p.is_file()}
                if kept_dir.is_dir()
                else {}
            )
            for file_name in sorted(set(fresh) | set(kept)):
                if fresh.get(file_name) != kept.get(file_name):
                    problems.append(f"{name}/{file_name} differs from rebuild")
    return {
        "claims": len(data["claims"]),
        "freeze_id": data["freeze_id"],
        "problems": problems,
    }


def audit_citations(paper_dir: Path) -> dict[str, Any]:
    cited: set[str] = set()
    for path in _tex_files(paper_dir):
        for group in _CITE.findall(path.read_text(encoding="utf-8")):
            cited.update(key.strip() for key in group.split(","))
    bib_keys = set(_BIBKEY.findall((paper_dir / "references.bib").read_text("utf-8")))
    with (paper_dir / "literature-matrix.csv").open(encoding="utf-8", newline="") as fh:
        rows = {row["key"]: row for row in csv.DictReader(fh)}
    problems: list[str] = []
    problems += [f"cited but not in bib: {k}" for k in sorted(cited - bib_keys)]
    problems += [f"bib entry not in literature matrix: {k}" for k in sorted(bib_keys - set(rows))]
    problems += [f"matrix row without bib entry: {k}" for k in sorted(set(rows) - bib_keys)]
    for key, row in sorted(rows.items()):
        if not row.get("source_url", "").strip() or not row.get("verified_via", "").strip():
            problems.append(f"matrix row not verified: {key}")
    return {
        "cited": len(cited),
        "bib_entries": len(bib_keys),
        "matrix_rows": len(rows),
        "uncited_bib_entries": sorted(bib_keys - cited),
        "problems": problems,
    }


def audit_claims(paper_dir: Path) -> dict[str, Any]:
    files = _tex_files(paper_dir) + sorted((paper_dir / "tables").glob("*.tex"))
    patterns = {name: re.compile(rx, re.IGNORECASE) for name, rx in PROHIBITED.items()}
    problems: list[str] = []
    for path in files:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            text = re.split(r"(?<!\\)%", line, maxsplit=1)[0]
            for name, pattern in patterns.items():
                if pattern.search(text):
                    problems.append(f"{path.name}:{number}: prohibited wording '{name}'")
            if _SUPERSEDED_X02.search(text) and not re.search(
                r"supersed|replaced", text, re.IGNORECASE
            ):
                problems.append(f"{path.name}:{number}: superseded X02 used as a result")
    return {"files": len(files), "problems": problems}


def run_audit(freeze_dir: Path, paper_dir: Path, *, numbers: bool = True) -> dict[str, Any]:
    data = json.loads((paper_dir / "data" / "paper-data.json").read_text("utf-8"))
    manuscript = audit_manuscript(_tex_files(paper_dir), data)
    report: dict[str, Any] = {
        "manuscript": {
            "used": len(manuscript["used"]),
            "unused": manuscript["unused"],
            "problems": [f"undefined {u}" for u in manuscript["undefined"]]
            + [f"typed decimal {t}" for t in manuscript["typed_decimals"]],
        },
        "citations": audit_citations(paper_dir),
        "claims": audit_claims(paper_dir),
    }
    if numbers:
        report["numerical"] = audit_numbers(freeze_dir, paper_dir)
    report["ok"] = not any(section["problems"] for section in report.values())
    return report

"""Phase 14: submission release candidate assembly, validation and manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from evaluation.research.release import assemble, manifest, release_record, validate

ROOT = Path(__file__).resolve().parents[1]


def _package(tmp: Path) -> Path:
    sub = tmp / "submission"
    (sub / "sections").mkdir(parents=True)
    (sub / "tables").mkdir()
    (sub / "figures").mkdir()
    (sub / "data").mkdir()
    (sub / "figures-static").mkdir()
    (sub / "figures-src").mkdir()
    (sub / "supplementary").mkdir()
    (sub / "manuscript.tex").write_text(
        "\\input{data/values.tex}\n\\input{sections/01-intro}\n", encoding="utf-8"
    )
    (sub / "sections" / "01-intro.tex").write_text(
        "\\widetable{tables/tab-a}\n\\includegraphics[width=\\linewidth]{figures/fig-a.pdf}\n"
        "% \\input{tables/commented-out}\n",
        encoding="utf-8",
    )
    (sub / "tables" / "tab-a.tex").write_text("table", encoding="utf-8")
    (sub / "figures" / "fig-a.pdf").write_bytes(b"%PDF-1.5")
    (sub / "data" / "values.tex").write_text("values", encoding="utf-8")
    (sub / "supplementary" / "S1.md").write_text("s1", encoding="utf-8")
    for name in (
        "manuscript.pdf",
        "references.bib",
        "README.md",
        "cover-letter.md",
        "AUTHOR_INPUT_REQUIRED.md",
        "REPRODUCIBILITY_STATUS.md",
        "ieeeaccess.cls",
    ):
        (sub / name).write_text(name, encoding="utf-8")
    (sub / "author-inputs.json").write_text(
        json.dumps(
            {"fields": [{"field": "Full author name(s)", "status": "NOT PROVIDED"}]}
        ),
        encoding="utf-8",
    )
    # Build intermediates and scratch that must never reach the package.
    (sub / "manuscript.aux").write_text("x", encoding="utf-8")
    (sub / "manuscript.log").write_text("x", encoding="utf-8")
    (sub / "sections" / "01-intro.tex.bak").write_text("x", encoding="utf-8")
    (sub / "literature-matrix.csv").write_text("audit only", encoding="utf-8")
    return sub


def test_release_candidate_is_clean_and_manifested(tmp_path: Path) -> None:
    sub = _package(tmp_path)
    compliance = tmp_path / "VENUE_COMPLIANCE.md"
    compliance.write_text("compliance", encoding="utf-8")
    rc = tmp_path / "rc"
    files = {p.relative_to(rc).as_posix() for p in assemble(sub, compliance, rc)}
    assert "manuscript.tex" in files and "ieeeaccess.cls" in files
    assert "VENUE_COMPLIANCE.md" in files
    assert not any(f.endswith((".aux", ".log", ".bak")) for f in files)
    assert "literature-matrix.csv" not in files

    result = validate(rc, compile_pdf=False)
    assert result["ok"], result["problems"]
    assert result["assets_checked"] == 4  # commented-out input is ignored

    record = manifest(rc, {"commit": "abc123", "paper_tree_dirty": False})
    entry = next(f for f in record["files"] if f["file"] == "tables/tab-a.tex")
    assert entry["sha256"] == hashlib.sha256(b"table").hexdigest()
    assert entry["size"] == 5 and entry["source_commit"] == "abc123"
    assert entry["purpose"] == "manuscript table"


def test_validation_reports_missing_assets_and_stray_files(tmp_path: Path) -> None:
    sub = _package(tmp_path)
    compliance = tmp_path / "VENUE_COMPLIANCE.md"
    compliance.write_text("c", encoding="utf-8")
    rc = tmp_path / "rc"
    assemble(sub, compliance, rc)
    (rc / "figures" / "fig-a.pdf").unlink()
    (rc / "stray.log").write_text("x", encoding="utf-8")
    problems = validate(rc, compile_pdf=False)["problems"]
    assert "missing asset figures/fig-a.pdf" in problems
    assert "build or development file in package: stray.log" in problems


def test_open_author_inputs_block_submission_ready(tmp_path: Path) -> None:
    sub = _package(tmp_path)
    compliance = tmp_path / "VENUE_COMPLIANCE.md"
    compliance.write_text("c", encoding="utf-8")
    rc = tmp_path / "rc"
    assemble(sub, compliance, rc)
    record = manifest(rc, {"commit": "abc123", "paper_tree_dirty": False})
    (rc / "MANIFEST.json").write_text(json.dumps(record), encoding="utf-8")
    release = release_record(
        ROOT,
        rc,
        record,
        {"ok": True, "pages": 13},
        {"paper": {"ok": True}},
        venue="IEEE Access",
        article_type="Applied Research",
        freeze="research/evidence/freeze-v2",
        publication="research/evidence/publication-v2",
    )
    assert release["verification"]["technical_checks_pass"] is True
    assert release["author_inputs_open"] == ["Full author name(s)"]
    assert release["submission_ready"] is False

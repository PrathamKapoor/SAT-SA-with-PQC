"""Phase 12: the manuscript's numbers, citations and wording trace to evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.research.paper import (
    audit_manuscript,
    build_paper_data,
    format_value,
    values_tex,
)
from evaluation.research.paper_audit import audit_citations, audit_claims

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"

# The paper's LaTeX sources are kept locally and are not published in the
# repository (since 2026-09-30). Manuscript checks run where they exist.
needs_paper_sources = pytest.mark.skipif(
    not (ROOT / "paper" / "manuscript.tex").exists(),
    reason="paper LaTeX sources are not in this checkout (kept locally, not published)",
)
FREEZE = ROOT / "research" / "evidence" / "freeze-v2"

pytestmark = pytest.mark.skipif(
    not (PAPER / "data" / "claims-spec.json").exists() or not FREEZE.exists(),
    reason="paper package or evidence freeze not present",
)


@pytest.fixture(scope="module")
def rebuilt() -> dict:
    return build_paper_data(FREEZE, PAPER / "data" / "claims-spec.json")


def _claims(data: dict) -> dict[str, dict]:
    return {c["claim_id"]: c for c in data["claims"]}


@needs_paper_sources
def test_paper_data_rebuilds_identically_from_freeze(rebuilt: dict) -> None:
    committed = json.loads((PAPER / "data" / "paper-data.json").read_text("utf-8"))
    assert rebuilt == committed
    assert values_tex(rebuilt) == (PAPER / "data" / "values.tex").read_text("utf-8")
    assert rebuilt["freeze_id"] == "satsa-evidence-freeze-v2"


def test_preserved_headline_values(rebuilt: dict) -> None:
    claims = _claims(rebuilt)
    expected = {
        "CODE-workers": "16",
        "A01-workers": "16",
        "X02b-rho-risk": "-0.11",
        "X02b-rho-risk-lo": "-0.42",
        "X02b-rho-risk-hi": "0.21",
        "X02b-rho-slowest": "0.94",
        "T01-detected": "13",
        "T01-expected": "13",
        "O02-recovered": "36",
        "O02-runs": "36",
        "D01-pass": "18",
        "R01b-match": "245",
    }
    for claim_id, display in expected.items():
        assert claims[claim_id]["display"] == display, claim_id
    # results come only from canonical bundles, never the superseded X02
    assert all(c["experiment_id"] != "X02" for c in rebuilt["claims"])


def test_every_claim_records_provenance(rebuilt: dict) -> None:
    for claim in rebuilt["claims"]:
        assert claim["source"], claim["claim_id"]
        if claim["experiment_id"] != "code":
            assert claim["source"].get("manifest_sha256") or claim["source"].get(
                "sha256"
            ), claim["claim_id"]


@needs_paper_sources
def test_manuscript_uses_only_defined_values_and_no_typed_decimals(
    rebuilt: dict,
) -> None:
    files = [PAPER / "manuscript.tex", *sorted((PAPER / "sections").glob("*.tex"))]
    report = audit_manuscript(files, rebuilt)
    assert report["undefined"] == []
    assert report["typed_decimals"] == []
    assert len(report["used"]) > 100


def test_audit_detects_typed_decimal_and_undefined_key(
    rebuilt: dict, tmp_path: Path
) -> None:
    tex = tmp_path / "bad.tex"
    tex.write_text(
        "Precision was 0.417 and \\V{NOPE-missing}; 95\\% is fine.\n", encoding="utf-8"
    )
    report = audit_manuscript([tex], rebuilt)
    assert report["undefined"] == ["bad.tex:1:NOPE-missing"]
    assert report["typed_decimals"] == ["bad.tex:1:0.417"]


@needs_paper_sources
def test_citations_are_verified_literature_rows() -> None:
    report = audit_citations(PAPER)
    assert report["problems"] == []
    assert report["bib_entries"] == report["matrix_rows"]


@needs_paper_sources
def test_manuscript_avoids_prohibited_claims(tmp_path: Path) -> None:
    assert audit_claims(PAPER)["problems"] == []
    fake = tmp_path / "paper"
    (fake / "sections").mkdir(parents=True)
    (fake / "tables").mkdir()
    (fake / "manuscript.tex").write_text("", encoding="utf-8")
    (fake / "sections" / "x.tex").write_text(
        "A novel, production-ready system with 17 analytical workers.\n"
        "X02 shows the result.\n",
        encoding="utf-8",
    )
    problems = audit_claims(fake)["problems"]
    assert any("novel" in p for p in problems)
    assert any("production" in p for p in problems)
    assert any("17 workers" in p for p in problems)
    assert any("superseded X02" in p for p in problems)


def test_format_value() -> None:
    assert format_value(0.0955, "{:.3f}") == "0.096"
    assert format_value(0.23, "pct0") == "23\\%"
    assert format_value(None, "int") == "n/a"
    assert format_value(-0.11, "signed2") == "-0.11"


def test_values_tex_uses_math_minus() -> None:
    tex = values_tex(
        {
            "freeze_id": "f",
            "claims": [{"claim_id": "A", "display": "-0.11"}],
        }
    )
    assert "\\@namedef{pv@A}{\\ensuremath{-}0.11}" in tex


def test_sih_safe_numbers_trace_to_paper_data(rebuilt: dict) -> None:
    sih = json.loads((ROOT / "research" / "sih-evidence.json").read_text("utf-8"))
    assert sih["schema"] == "satsa-sih-evidence/3"
    claims = _claims(rebuilt)
    for item in sih["safe_demo_numbers"]:
        assert item["context"], item["say"]
        for claim_id in item["claim_ids"]:
            assert claims[claim_id]["display"] in item["say"], (claim_id, item["say"])
    steps = [s["step"] for s in sih["demo_flow"]["steps"]]
    assert steps[0] == "LOGIN" and steps[-1] == "VERIFICATION"
    assert len(steps) == 13


@needs_paper_sources
def test_publication_snapshot_verifies_and_detects_tampering(tmp_path: Path) -> None:
    from evaluation.research.publication import build_publication, verify_publication

    out = tmp_path / "publication-test"
    record = build_publication(
        PAPER,
        FREEZE,
        out,
        publication_id="publication-test",
        paper_commit="test",
        manuscript_version="test",
        literature_snapshot_date="2026-09-27",
    )
    assert record["freeze"]["freeze_id"] == "satsa-evidence-freeze-v2"
    assert "paper/data/paper-data.json" in record["files"]
    assert not any(name.endswith(".aux") for name in record["files"])
    assert verify_publication(out, repo_root=ROOT)["intact"]
    with pytest.raises(FileExistsError):
        build_publication(
            PAPER,
            FREEZE,
            out,
            publication_id="again",
            paper_commit="test",
            manuscript_version="test",
            literature_snapshot_date="2026-09-27",
        )
    values = out / "paper" / "data" / "values.tex"
    values.write_text(values.read_text("utf-8") + "% edit\n", encoding="utf-8")
    (out / "paper" / "extra.txt").write_text("x", encoding="utf-8")
    problems = verify_publication(out, repo_root=ROOT)["problems"]
    assert "hash mismatch paper/data/values.tex" in problems
    assert "unlisted file paper/extra.txt" in problems


@needs_paper_sources
def test_generated_tables_and_figures_match_freeze() -> None:
    pytest.importorskip("matplotlib")
    from evaluation.research.paper_audit import audit_numbers

    report = audit_numbers(FREEZE, PAPER)
    assert report["problems"] == []

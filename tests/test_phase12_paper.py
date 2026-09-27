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


def test_citations_are_verified_literature_rows() -> None:
    report = audit_citations(PAPER)
    assert report["problems"] == []
    assert report["bib_entries"] == report["matrix_rows"]


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


def test_generated_tables_and_figures_match_freeze() -> None:
    pytest.importorskip("matplotlib")
    from evaluation.research.paper_audit import audit_numbers

    report = audit_numbers(FREEZE, PAPER)
    assert report["problems"] == []

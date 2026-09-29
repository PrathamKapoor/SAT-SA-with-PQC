"""The frozen paper's code facts are independent of the evolving product.

The paper describes the code at the freeze's canonical commit; the product
keeps changing after it. These tests keep the two apart: the live API may
grow, the paper's historical facts may not.
"""

import json
from pathlib import Path

import pytest

from evaluation.research.paper import (
    PAPER_CODE_FACTS,
    PAPER_CODE_FACTS_COMMIT,
    _code_fact,
    build_paper_data,
    paper_code_fact,
)

ROOT = Path(__file__).resolve().parents[1]

# The research paper and its evidence (paper/, research/) are kept locally and
# are not published in the repository. These checks run where they exist.
_REPO = Path(__file__).resolve().parents[1]
needs_research_artifacts = pytest.mark.skipif(
    not ((_REPO / "paper").is_dir() and (_REPO / "research" / "evidence").is_dir()),
    reason="research paper and evidence are not in this checkout (kept locally, not published)",
)

# The paper's LaTeX sources are kept locally and are not published in the
# repository (since 2026-09-30). Manuscript checks run where they exist.
needs_paper_sources = pytest.mark.skipif(
    not (ROOT / "paper" / "manuscript.tex").exists(),
    reason="paper LaTeX sources are not in this checkout (kept locally, not published)",
)
FREEZE = ROOT / "research" / "evidence" / "freeze-v2"
PAPER = ROOT / "paper"


def _freeze_record() -> dict:
    return json.loads((FREEZE / "freeze.json").read_text(encoding="utf-8"))


def _committed_claims(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {c["claim_id"]: c for c in data["claims"]}


@needs_paper_sources
def test_live_api_and_historical_paper_route_counts_differ():
    # Current product contract (docs/API_CONTRACT.md): 44 routes at the
    # freeze plus GET /api/v1/priorities and GET /api/v1/versions/{id}/records.
    assert _code_fact("api_route_count") == 46
    assert paper_code_fact("api_route_count", _freeze_record()) == 44
    for data in (PAPER / "data", PAPER / "submission" / "data"):
        claim = _committed_claims(data / "paper-data.json")["CODE-api-routes"]
        assert claim["value"] == 44
        assert "\\@namedef{pv@CODE-api-routes}{44}" in (data / "values.tex").read_text(
            encoding="utf-8"
        )


@needs_research_artifacts
def test_every_cited_code_fact_is_pinned_to_the_freeze_commit():
    record = _freeze_record()
    assert record["canonical_code_commit"] == PAPER_CODE_FACTS_COMMIT
    spec = json.loads((PAPER / "data" / "claims-spec.json").read_text("utf-8"))
    committed = _committed_claims(PAPER / "data" / "paper-data.json")
    cited = [c for c in spec["claims"] if "code_fact" in c]
    assert cited
    for item in cited:
        fact = item["code_fact"]
        assert fact in PAPER_CODE_FACTS, fact
        assert PAPER_CODE_FACTS[fact]["derivation"]
        assert committed[item["claim_id"]]["value"] == PAPER_CODE_FACTS[fact]["value"]


@needs_research_artifacts
def test_pinned_facts_refuse_a_different_freeze_commit():
    with pytest.raises(ValueError, match="pinned"):
        paper_code_fact("api_route_count", {"canonical_code_commit": "0" * 40})
    with pytest.raises(KeyError):
        paper_code_fact("unpinned_fact", _freeze_record())


@needs_research_artifacts
def test_paper_data_rebuild_ignores_live_route_changes(monkeypatch):
    from evaluation.research import paper

    monkeypatch.setattr(paper, "_code_fact", lambda name: 999)
    rebuilt = build_paper_data(FREEZE, PAPER / "data" / "claims-spec.json")
    committed = json.loads((PAPER / "data" / "paper-data.json").read_text("utf-8"))
    assert rebuilt == committed

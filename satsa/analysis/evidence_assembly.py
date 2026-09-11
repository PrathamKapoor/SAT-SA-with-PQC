"""Evidence & Explainability Assembly: one canonical WHAT/WHY/EVIDENCE/
CONFIDENCE/LIMITATIONS/RECOMMENDATION decomposition for any finding,
built once instead of duplicated per caller.

Before this module, ``satsa/ui/__init__.py``'s ``finding_detail``
route parsed ``confidence_json``, resolved ``evidence_refs``, and
called ``recommend()`` inline; ``satsa/analysis/report.py`` separately
re-implemented its own ``confidence_json`` parsing for the same
finding shape. A pure function here (no database access — callers
resolve evidence rows and pass them in, keeping this testable without
a DB fixture) gives both a single source of truth.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class ExplanationBundle:
    finding_id: str
    rule_or_category: str
    what: str          # human-readable label derived from rule_or_category
    why: str            # the finding's own rationale
    evidence: list = field(default_factory=list)       # resolved source records
    confidence: dict = field(default_factory=dict)     # parsed confidence_json
    limitations: str = ""
    recommendation: dict = field(default_factory=dict)  # from satsa.analysis.recommend
    drill_down: dict = field(default_factory=dict)      # observation_id/worker_name/etc.

    def to_dict(self) -> dict:
        return {
            "finding_id": self.finding_id,
            "rule_or_category": self.rule_or_category,
            "what": self.what, "why": self.why,
            "evidence": list(self.evidence),
            "confidence": dict(self.confidence),
            "limitations": self.limitations,
            "recommendation": dict(self.recommendation),
            "drill_down": dict(self.drill_down),
        }


def _humanize_rule(rule_or_category: str) -> str:
    """`execution_gap.fast_closure` -> `Execution Gap: Fast Closure`."""
    if not rule_or_category:
        return "Unknown finding"
    parts = rule_or_category.split(".")
    return ": ".join(p.replace("_", " ").title() for p in parts)


def assemble_explanation(
    finding: dict, *, evidence_records: list[dict] | None = None,
    observation: dict | None = None,
) -> ExplanationBundle:
    """Build the uniform explanation bundle for one finding row.

    ``finding`` is a ``satsa_findings`` row (dict-like). ``evidence_records``
    is the caller-resolved list of ``satsa_source_records`` rows the
    finding's ``evidence_refs_json`` points to (this function does not
    touch the database itself — callers already have a connection open
    and resolving here would duplicate that access pattern, not
    simplify it). ``observation`` is the optional parent
    ``satsa_observations`` row, used only for drill-down metadata.
    """
    from satsa.analysis.recommend import recommend

    try:
        confidence = json.loads(finding.get("confidence_json") or "{}")
    except (TypeError, ValueError):
        confidence = {}

    rec = recommend(finding)
    rec_dict = rec.to_dict() if hasattr(rec, "to_dict") else dict(rec)

    drill_down = {
        "observation_id": finding.get("observation_id", ""),
        "worker_name": (observation or {}).get("worker_name", "")
                       or finding.get("worker_name", ""),
        "run_id": (observation or {}).get("run_id", ""),
        "entity_id": (observation or {}).get("entity_id", ""),
        "assessment_id": (observation or {}).get("assessment_id", ""),
    }

    return ExplanationBundle(
        finding_id=finding.get("id", ""),
        rule_or_category=finding.get("rule_or_category", ""),
        what=_humanize_rule(finding.get("rule_or_category", "")),
        why=finding.get("rationale", ""),
        evidence=list(evidence_records or []),
        confidence=confidence,
        limitations=finding.get("limitations", ""),
        recommendation=rec_dict,
        drill_down=drill_down,
    )

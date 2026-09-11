"""Correlation & Signal Fusion: cross-finding corroboration clustering.

Genuinely distinct from ``satsa.analysis.risk``'s entity risk scoring
(the "Fusion Agent" / ``compute_entity_risk``): risk scoring answers
"how much total risk does this entity carry, broken down by dimension
weight" (see ``risk.py``'s module docstring). Signal fusion answers a
different, earlier question — "do multiple independent detectors agree
about the same underlying incident?" Corroboration across detector
*families* (e.g. an ``execution_gap`` finding and a ``negative_space``
finding that both name the same case) is stronger supervisory evidence
than either finding alone, and before this module existed it was
invisible: two findings from different dimensions that both reference
the same underlying case were summed into their own dimension buckets
with no cross-reference showing a supervisor *why* two dimensions both
fired.

This module clusters findings by shared ``scoped_subjects`` (entity/
asset/case/alert ids present on more than one finding) and flags
clusters where two or more distinct rule *families* point at the same
subject. It is purely additive: it does not alter ``risk.py``'s score
computation (``DIMENSION_WEIGHTS`` / the saturating per-dimension
curve are untouched); it surfaces the corroboration structure as its
own evidence object on ``EntityRiskProfile.correlation_clusters`` so a
supervisor can see the cross-reference directly instead of reasoning
about it from two unrelated dimension rows.

Deterministic and purely structural — grouping by a shared identifier,
not a statistical inference — so unlike a threshold-based detector it
needs no baseline/ablation validation to be trustworthy: the claim is
"these finding ids share a subject id," which is directly checkable
against the stored rows, not an inferred probability.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field


def rule_family(rule: str) -> str:
    """First dot-segment of a rule_or_category, e.g.
    'execution_gap.fast_closure' -> 'execution_gap'."""
    return rule.split(".", 1)[0] if rule else "unknown"


def _subjects(finding: dict) -> list:
    raw = finding.get("scoped_subjects_json")
    if raw is None:
        raw = finding.get("scoped_subjects", [])
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return []
    return [str(s) for s in (raw or [])]


@dataclass
class CorrelationCluster:
    subject: str
    finding_ids: list = field(default_factory=list)
    rule_families: list = field(default_factory=list)
    corroborated: bool = False
    rationale: str = ""

    def to_dict(self) -> dict:
        return {
            "subject": self.subject,
            "finding_ids": list(self.finding_ids),
            "rule_families": list(self.rule_families),
            "corroborated": self.corroborated,
            "rationale": self.rationale,
        }


def correlate_findings(finding_rows: list) -> list:
    """Group findings that share at least one ``scoped_subjects`` id.

    A cluster is marked ``corroborated`` when two or more distinct
    rule families reference the same subject — independent evidence
    about the same underlying incident, not the same detector firing
    twice on the same subject (which is expected and not, by itself,
    corroboration). Subjects referenced by only one finding are not
    clusters and are omitted.
    """
    by_subject: dict = {}
    for f in finding_rows:
        for s in _subjects(f):
            by_subject.setdefault(s, []).append(f)

    clusters: list = []
    for subject, findings in sorted(by_subject.items()):
        if len(findings) < 2:
            continue
        # de-duplicate by finding id: a worker could list the same
        # subject twice within its own scoped_subjects
        seen_ids = set()
        unique_findings = []
        for f in findings:
            fid = f.get("id")
            if fid in seen_ids:
                continue
            seen_ids.add(fid)
            unique_findings.append(f)
        if len(unique_findings) < 2:
            continue
        families = sorted({rule_family(f.get("rule_or_category", ""))
                            for f in unique_findings})
        corroborated = len(families) >= 2
        if corroborated:
            rationale = (
                f"{len(unique_findings)} finding(s) from {len(families)} "
                f"distinct detector families ({', '.join(families)}) all "
                f"reference subject {subject!r} — independent "
                "corroboration, not the same detector firing twice.")
        else:
            rationale = (
                f"{len(unique_findings)} finding(s) from the same "
                f"detector family ({families[0]}) reference subject "
                f"{subject!r}; not cross-family corroboration.")
        clusters.append(CorrelationCluster(
            subject=subject,
            finding_ids=[f["id"] for f in unique_findings],
            rule_families=families,
            corroborated=corroborated,
            rationale=rationale,
        ))
    return clusters


def corroborated_clusters(clusters: list) -> list:
    """The subset of clusters with cross-family corroboration —
    what a supervisor UI should highlight first."""
    return [c for c in clusters if c.corroborated]

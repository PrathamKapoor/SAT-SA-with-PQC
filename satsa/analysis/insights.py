"""Cross-entity supervisory insights: simple, explainable
aggregations across the deployment.

These are NOT black-box "AI insights". Every insight has:
* a title,
* a short description of the pattern,
* the affected entities,
* a statistical basis (count, percentage),
* a confidence bucket,
* explicit limitations.

The insights are computed from the existing risk / finding data
already in the database, so no new worker is required.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


def cross_entity_aggregate(engine, assessment_id: str, exclude_entity_id: str) -> dict:
    """Aggregate signal findings for the given ``assessment_id`` across
    every entity EXCEPT ``exclude_entity_id`` (i.e. across the
    *other* entities in the same assessment period).

    Returns a dict shaped as::

        {
            "n_other_entities": int,
            "n_other_finding_rows": int,
            "by_rule": { rule: {"count": int, "entity_ids": [..]} },
        }

    The aggregate is the data the CrossEntityInsightsWorker consumes
    via the supervisor's ``extras`` channel. If no other entity has
    a completed/partial run yet in this assessment, ``by_rule`` is
    empty and the worker abstains honestly — never fabricates a
    cross-entity insight from this entity alone.
    """
    by_rule: dict[str, dict] = {}
    rows = engine.query_all(
        "SELECT o.entity_id, f.rule_or_category"
        " FROM satsa_findings f"
        " JOIN satsa_observations o ON o.id = f.observation_id"
        " JOIN satsa_runs r ON r.id = o.run_id"
        " WHERE r.assessment_id = ? AND r.status IN ('completed','partial')"
        "   AND o.entity_id != ? AND f.state = 'signal'",
        (assessment_id, exclude_entity_id),
    )
    for r in rows:
        rule = r.get("rule_or_category") or "unknown"
        eid = r.get("entity_id") or "unknown"
        slot = by_rule.setdefault(rule, {"count": 0, "entity_ids": []})
        slot["count"] += 1
        if eid not in slot["entity_ids"]:
            slot["entity_ids"].append(eid)
    return {
        "n_other_entities": len({r.get("entity_id") for r in rows if r.get("entity_id")}),
        "n_other_finding_rows": len(rows),
        "by_rule": by_rule,
    }


@dataclass
class CrossInsight:
    title: str
    description: str
    affected_entities: list
    statistical_basis: dict
    confidence: str
    limitations: str

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "affected_entities": list(self.affected_entities),
            "statistical_basis": dict(self.statistical_basis),
            "confidence": self.confidence,
            "limitations": self.limitations,
        }


def _format_entity_list(rows: list) -> list:
    return [
        {"entity_id": r["entity_id"], "display_name": r.get("display_name", "")}
        for r in rows
    ]


def common_execution_gap(engine, *, min_entities: int = 2) -> Optional[CrossInsight]:
    """If multiple entities share the same top execution-gap rule,
    surface it as a 'common control weakness' insight."""
    rows = engine.query_all(
        "SELECT e.id AS entity_id, e.display_name, f.rule_or_category,"
        " COUNT(*) AS c FROM satsa_findings f"
        " JOIN satsa_observations o ON o.id=f.observation_id"
        " JOIN satsa_entities e ON e.id=o.entity_id"
        " WHERE f.state='signal' AND f.rule_or_category LIKE 'execution_gap.%'"
        " GROUP BY e.id, e.display_name, f.rule_or_category"
        " ORDER BY c DESC")
    if not rows:
        return None
    by_rule: dict[str, list] = {}
    for r in rows:
        by_rule.setdefault(r["rule_or_category"], []).append(r)
    # pick the rule with the most distinct entities
    best = max(by_rule.items(), key=lambda kv: len(kv[1]))
    rule, hits = best
    if len(hits) < min_entities:
        return None
    return CrossInsight(
        title=f"Recurring execution-gap pattern: {rule}",
        description=(
            f"{len(hits)} entities in the deployment share the same "
            f"top execution-gap rule ({rule}). This suggests a "
            f"control-weakness pattern that may benefit from a "
            f"sector-wide remediation rather than entity-by-entity "
            f"fixes."
        ),
        affected_entities=_format_entity_list(hits),
        statistical_basis={
            "rule": rule,
            "entities_with_rule": len(hits),
            "total_signal_findings": sum(r["c"] for r in hits),
        },
        confidence="medium",
        limitations=(
            "Identical rules do not prove a shared root cause; the "
            "CSEs may have reached the same shape for different "
            "reasons. Treat as a hypothesis to investigate, not a "
            "conclusion."
        ),
    )


def common_negative_space(engine, *, min_entities: int = 2) -> Optional[CrossInsight]:
    """If multiple entities are missing the same kind of evidence,
    surface a 'common monitoring gap' insight."""
    rows = engine.query_all(
        "SELECT entity_id, display_name, missing FROM ("
        " SELECT e.id AS entity_id, e.display_name, j.value AS missing"
        " FROM satsa_entities e,"
        " json_each((SELECT s.ingest_report_json FROM satsa_submissions s"
        "            WHERE s.entity_id=e.id AND s.assessment_id IN"
        "              (SELECT id FROM satsa_assessments WHERE entity_id=e.id"
        "               ORDER BY period_start DESC LIMIT 1)) ,"
        "            '$.categories') AS j"
        " WHERE j.value IS NULL OR j.value = ''"
        ")")
    # Simpler: use the existing negative_space.missing_file.* rules
    rows = engine.query_all(
        "SELECT e.id AS entity_id, e.display_name, f.rule_or_category"
        " FROM satsa_findings f"
        " JOIN satsa_observations o ON o.id=f.observation_id"
        " JOIN satsa_entities e ON e.id=o.entity_id"
        " WHERE f.rule_or_category LIKE 'negative_space.missing_file.%'"
        " GROUP BY e.id, e.display_name, f.rule_or_category"
        " ORDER BY e.id")
    if not rows:
        return None
    by_missing: dict[str, list] = {}
    for r in rows:
        missing = r["rule_or_category"].split(".")[-1]
        by_missing.setdefault(missing, []).append(r)
    best = max(by_missing.items(), key=lambda kv: len(kv[1]))
    missing, hits = best
    if len(hits) < min_entities:
        return None
    return CrossInsight(
        title=f"Common monitoring gap: missing {missing} file",
        description=(
            f"{len(hits)} entities in the deployment are missing the "
            f"`{missing}` category from their submissions. This is a "
            f"common data-quality gap that may indicate a sector-wide "
            f"ingestion or reporting process problem."
        ),
        affected_entities=_format_entity_list(hits),
        statistical_basis={
            "missing_file": missing,
            "entities_affected": len(hits),
        },
        confidence="high",
        limitations=(
            "Missing-file findings are data-completeness signals, not "
            "behaviour signals. They do not indicate that the entity "
            "is misbehaving — only that the submission is incomplete."
        ),
    )


def sector_deviation(engine) -> Optional[CrossInsight]:
    """If an entity's total risk score is an outlier within its
    cohort (sector + environment), surface a sector-specific
    deviation."""
    rows = engine.query_all(
        "SELECT e.id AS entity_id, e.display_name, e.sector, e.environment_class"
        " FROM satsa_entities e")
    if len(rows) < 3:
        return None  # need a cohort of at least 3
    # For now, signal the entity with the highest total_score in each
    # cohort. A full outlier analysis (IQR / MAD) is left to the
    # anomaly worker.
    # Get latest run per entity
    latest = {}
    for r in rows:
        run = engine.query_one(
            "SELECT id, total_score FROM satsa_runs WHERE entity_id=?"
            " AND status IN ('completed','partial')"
            " ORDER BY created_at DESC LIMIT 1", (r["entity_id"],))
        if run:
            latest[r["entity_id"]] = (r, run["total_score"])
    if len(latest) < 3:
        return None
    by_sector: dict[tuple, list] = {}
    for eid, (row, score) in latest.items():
        by_sector.setdefault((row["sector"], row["environment_class"]), []).append((eid, row, score))
    out: list[CrossInsight] = []
    for cohort, members in by_sector.items():
        if len(members) < 3:
            continue
        members.sort(key=lambda m: m[2], reverse=True)
        top = members[0]
        out.append(CrossInsight(
            title=f"Sector deviation: {cohort[0]} / {cohort[1]}",
            description=(
                f"{top[1]['display_name']} has the highest total risk "
                f"score in its {cohort[0]} / {cohort[1]} cohort "
                f"(score={top[2]}). It warrants prioritised examiner "
                f"attention relative to its peers."
            ),
            affected_entities=[{"entity_id": top[0], "display_name": top[1]["display_name"]}],
            statistical_basis={
                "cohort": f"{cohort[0]} / {cohort[1]}",
                "cohort_size": len(members),
                "top_score": top[2],
            },
            confidence="high",
            limitations=(
                "This is a ranking, not a calibrated risk score. The "
                "deviation may reflect a genuine posture problem or "
                "a more thorough submission by the outlier."
            ),
        ))
    if not out:
        return None
    # Return the most extreme one
    out.sort(key=lambda i: i.statistical_basis["top_score"], reverse=True)
    return out[0]


def all_insights(engine) -> list[CrossInsight]:
    """Run all cross-entity insight builders and return the non-None
    results."""
    out: list[CrossInsight] = []
    for fn in (common_execution_gap, common_negative_space, sector_deviation):
        r = fn(engine)
        if r is not None:
            out.append(r)
    return out

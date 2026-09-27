"""Failure analysis for the external IT incident-log evaluation (EXP-X02).

Diagnoses why SAT-SA's entity risk did not track the groups' SLA-miss rate,
without changing any detector, threshold or risk weight and without tuning on
the evaluation data. Uses the same source file, adapter version and entity
construction as X02. Produces, per assignment group:

* detector firing, finding counts, statistics and confidence;
* the prevalence of each saturating detector's *input condition*, computed
  directly from the mapped records with the detector's own thresholds;
* the risk decomposition by dimension;
* label and temporal checks from the raw event log.

It then relates prevalence, risk and SLA-miss rate with Spearman
correlations (bootstrap intervals over groups). No threshold is changed.
"""

from __future__ import annotations

import json
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from evaluation.research.external_itsm import _spearman_interval, spearman

EXPERIMENT_NAME = "satsa-external-itsm-failure-analysis-v1"

# Rule type of each detector family observed on the external data, read from
# the worker code (satsa/analysis/workers/*). "existence" = fires when at
# least one qualifying record exists; "distribution" = within-entity tail
# outliers; "cohort" = deviation from a peer cohort.
RULE_TYPES = {
    "execution_gap.ack_without_investigation": "existence (any medium+ alert whose case has < 2 steps)",
    "negative_space.missing_investigation": "existence (any case with 0 steps)",
    "case_similarity.template_cluster": "existence (any cluster of >= 2 near-identical step sequences)",
    "execution_gap.fast_closure": "existence (any alert closed faster than its severity limit, >= 30 s)",
    "anomaly.investigation_depth.high": "distribution (> 3 MAD within the entity; capped at 20)",
    "anomaly.closure_time.high": "distribution (> 3 MAD within the entity; capped at 20)",
    "anomaly.investigation_duration.high": "distribution (> 3 MAD within the entity; capped at 20)",
    "execution_gap.critical_without_escalation": "existence (any critical alert without escalation)",
    "negative_space.missing_escalation": "existence (expected escalation absent)",
    "peer_benchmark": "cohort (> 2 MAD from peer median, >= 3 peers)",
    "execution_gap.repeated_investigation_pattern": "rate or note-length rule "
    "(dominant step pair >= 60% of pairs, or median note < 30 chars; the "
    "source has no notes, so the adapter's empty notes always satisfy it)",
    "execution_gap.potential_metric_gaming": "rate (critical/high closure rate "
    ">= 90% with <= 1.5 average steps)",
    "anomaly.escalation_rate.low": "distribution (> 3 MAD within the entity)",
    "workflow_reconstruction.sequence_chronology_mismatch": "existence (any "
    "case whose step sequence disagrees with timestamps)",
}

# Construct validity of each signal on UCI-498 (see adapter mapping).
CONSTRUCTS = [
    {
        "concept": "alert workload",
        "source": "incident count per final group",
        "classification": "directly observed",
        "measures_satsa_concept": "yes (volume only)",
    },
    {
        "concept": "closure behaviour",
        "source": "resolved_at - opened_at",
        "classification": "directly observed",
        "measures_satsa_concept": "partly: SAT-SA treats unusually fast closure of "
        "security alerts as a possible skipped investigation; in IT service "
        "management fast resolution is the service goal",
    },
    {
        "concept": "acknowledgement",
        "source": "first non-New event time",
        "classification": "derived",
        "measures_satsa_concept": "approximately",
    },
    {
        "concept": "investigation quality",
        "source": "number of Active/Awaiting state events",
        "classification": "proxy",
        "measures_satsa_concept": "no: state changes are not investigation steps; "
        "ITSM tickets often resolve directly from New",
    },
    {
        "concept": "escalation quality",
        "source": "reassignment_count increments",
        "classification": "proxy",
        "measures_satsa_concept": "no: reassignment routes work, it is not a "
        "severity escalation",
    },
    {
        "concept": "disposition quality",
        "source": "closed_code (anonymized)",
        "classification": "proxy",
        "measures_satsa_concept": "no: outcome semantics unavailable",
    },
    {
        "concept": "evidence completeness / monitoring coverage",
        "source": "assets (cmdb_ci known for 54 of 24,918 incidents)",
        "classification": "unavailable",
        "measures_satsa_concept": "not evaluable",
    },
    {
        "concept": "peer deviation",
        "source": "groups of one organisation compared on the metrics above",
        "classification": "derived",
        "measures_satsa_concept": "only as valid as the underlying proxy metrics",
    },
    {
        "concept": "external outcome: SLA miss",
        "source": "final made_sla flag",
        "classification": "directly observed",
        "measures_satsa_concept": "no: timeliness against a service target, not "
        "supervisory execution quality",
    },
]


def _prevalence(engine, entity_id: str) -> dict[str, float]:
    """Input-condition prevalence using the detectors' default thresholds."""
    from satsa.analysis.workers.ack_without_investigation import (
        DEFAULT_ACK_WITHOUT_INVESTIGATION_POLICY as ack,
    )
    from satsa.analysis.workers.fast_closure import (
        DEFAULT_FAST_CLOSURE_POLICY as fast,
    )
    from satsa.analysis.workers.fast_closure import _threshold_for

    alerts = engine.query_all(
        "SELECT id,mapped_severity,created_at,closed_at,case_refs_json FROM satsa_alerts"
        " WHERE entity_id=?",
        (entity_id,),
    )
    cases = engine.query_all(
        "SELECT id FROM satsa_cases WHERE entity_id=?", (entity_id,)
    )
    steps = Counter(
        row["case_id"]
        for row in engine.query_all(
            "SELECT s.case_id FROM satsa_investigation_steps s JOIN satsa_cases c"
            " ON c.id=s.case_id WHERE c.entity_id=?",
            (entity_id,),
        )
    )
    closes = [
        (a, float(a["closed_at"]) - float(a["created_at"]))
        for a in alerts
        if a["closed_at"] is not None
    ]
    fast_count = sum(
        1
        for a, seconds in closes
        if a["mapped_severity"] in {"critical", "high", "medium"}
        and fast.absolute_floor_seconds
        <= seconds
        < _threshold_for(a["mapped_severity"], fast)
    )
    eligible = [a for a in alerts if a["mapped_severity"] in ack.severities]
    shallow = 0
    for a in eligible:
        refs = json.loads(a["case_refs_json"] or "[]")
        if refs and all(steps.get(ref, 0) < ack.min_steps_per_case for ref in refs):
            shallow += 1
    return {
        "incidents": float(len(alerts)),
        "cases_without_steps_rate": sum(steps.get(c["id"], 0) == 0 for c in cases)
        / max(1, len(cases)),
        "alerts_with_under_2_steps_rate": shallow / max(1, len(eligible)),
        "fast_closure_rate": fast_count / max(1, len(closes)),
        "median_resolution_hours": (
            statistics.median(s for _, s in closes) / 3600 if closes else 0.0
        ),
        "median_steps_per_case": statistics.median(
            [steps.get(c["id"], 0) for c in cases]
        )
        if cases
        else 0.0,
    }


def _label_checks(source_csv: Path, groups: set[str]) -> dict[str, Any]:
    """Temporal and attribution checks from the raw event log."""
    from public_benchmarks.itsm_incident_log.adapter import load_incidents, parse_time

    incidents = load_incidents(source_csv)
    checks: Counter = Counter()
    miss_by_reassignment: dict[str, list[bool]] = defaultdict(list)
    for events in incidents.values():
        last = events[-1]
        if last["assignment_group"] not in groups:
            continue
        missed = last["made_sla"] == "false"
        reassigned = int(last["reassignment_count"]) > 0
        miss_by_reassignment["reassigned" if reassigned else "not_reassigned"].append(
            missed
        )
        checks["incidents"] += 1
        if missed:
            checks["sla_missed"] += 1
            flip = next((e for e in events if e["made_sla"] == "false"), None)
            if (
                flip is not None
                and flip["assignment_group"] != last["assignment_group"]
            ):
                checks["sla_flip_while_held_by_other_group"] += 1
            if (
                flip is not None
                and last["resolved_at"] not in ("", "?")
                and (parse_time(flip["sys_updated_at"]) or 0)
                > (parse_time(last["resolved_at"]) or 0)
            ):
                checks["sla_flip_recorded_after_resolution"] += 1
        values = {e["made_sla"] for e in events}
        if values == {"false", "true"}:
            order = [e["made_sla"] for e in events]
            if (
                order.index("false") < len(order) - 1
                and "true" in order[order.index("false") :]
            ):
                checks["sla_flag_returned_to_true"] += 1
    return {
        "counts": dict(checks),
        "sla_miss_rate_reassigned": statistics.fmean(miss_by_reassignment["reassigned"])
        if miss_by_reassignment["reassigned"]
        else None,
        "sla_miss_rate_not_reassigned": statistics.fmean(
            miss_by_reassignment["not_reassigned"]
        )
        if miss_by_reassignment["not_reassigned"]
        else None,
        "notes": [
            "made_sla is read only from the final event; SAT-SA never receives it",
            "risk and label are computed over the same incidents and the same period",
        ],
    }


def run_external_failure_analysis(
    scratch_dir: Path,
    *,
    source_csv: Path,
    expected_source_sha256: str | None = None,
    min_incidents: int = 30,
    seed: int = 0,
) -> dict[str, Any]:
    from evaluation.ablation.runner import _emitted_families
    from public_benchmarks.itsm_incident_log.adapter import (
        build_submissions,
        sha256_file,
    )
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    from satsa.analysis.risk import compute_entity_risk
    from satsa.service import SatsaService

    source_csv = Path(source_csv)
    if expected_source_sha256 and sha256_file(source_csv) != expected_source_sha256:
        raise ValueError("source file checksum does not match the recorded download")
    root = Path(scratch_dir)
    root.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    report = build_submissions(
        source_csv, root / "derived", min_incidents=min_incidents
    )
    period = report["assessment_period"]
    engine = SQLiteDatabaseEngine(root / "failure.sqlite3")
    engine.connect()
    groups: dict[str, dict[str, Any]] = {}
    try:
        MigrationRunner(engine).migrate()
        service = SatsaService(engine)
        for directory in sorted((root / "derived" / "submissions").iterdir()):
            entity = service.register_entity(
                directory.name,
                sector="itsm-public-dataset",
                environment_class="uci-498",
            )
            assessment = service.open_assessment(
                entity.id, period["start"], period["end"]
            )
            service.submit(assessment.id, directory)
            groups[directory.name] = {
                "entity_id": entity.id,
                "assessment_id": assessment.id,
            }
        for info in groups.values():
            run = service.run_analysis(info["entity_id"], info["assessment_id"])
            findings = engine.query_all(
                "SELECT rule_or_category,statistic,effect,threshold,confidence_json"
                " FROM satsa_findings f JOIN satsa_observations o ON o.id=f.observation_id"
                " WHERE o.run_id=? AND f.state='signal'",
                (run.run_id,),
            )
            by_family: dict[str, dict[str, Any]] = {}
            for row in findings:
                family = row["rule_or_category"]
                entry = by_family.setdefault(
                    family, {"findings": 0, "statistics": [], "confidence": []}
                )
                entry["findings"] += 1
                entry["statistics"].append(row["statistic"])
                entry["confidence"].append(
                    json.loads(row["confidence_json"] or "{}").get("overall")
                )
            profile = compute_entity_risk(engine, info["entity_id"], run_id=run.run_id)
            info.update(
                {
                    "families": sorted(_emitted_families(engine, run.run_id)),
                    "findings_by_family": by_family,
                    "risk_total": round(profile.total_score, 4),
                    "risk_dimensions": {d.name: d.score for d in profile.dimensions},
                    "prevalence": _prevalence(engine, info["entity_id"]),
                }
            )
    finally:
        engine.close()

    labels = json.loads((root / "derived" / "labels.json").read_text(encoding="utf-8"))
    names = sorted(groups)
    miss = [labels["groups"][n.replace("_", " ")]["sla_miss_rate"] for n in names]
    risk = [groups[n]["risk_total"] for n in names]

    def assoc(values: list[float], other: list[float], offset: int) -> dict[str, Any]:
        return {
            "spearman_rho": spearman(values, other),
            "bootstrap_interval": _spearman_interval(values, other, seed + offset),
        }

    prevalence_keys = list(groups[names[0]]["prevalence"])
    prevalence_vs_sla = {
        key: assoc([groups[n]["prevalence"][key] for n in names], miss, i)
        for i, key in enumerate(prevalence_keys)
    }
    prevalence_vs_risk = {
        key: assoc([groups[n]["prevalence"][key] for n in names], risk, 100 + i)
        for i, key in enumerate(prevalence_keys)
    }
    dimension_names = list(groups[names[0]]["risk_dimensions"])
    dimensions = {
        dim: {
            "groups_nonzero": sum(groups[n]["risk_dimensions"][dim] > 0 for n in names),
            "distinct_values": len({groups[n]["risk_dimensions"][dim] for n in names}),
            "min": min(groups[n]["risk_dimensions"][dim] for n in names),
            "max": max(groups[n]["risk_dimensions"][dim] for n in names),
            "vs_sla_miss": assoc(
                [groups[n]["risk_dimensions"][dim] for n in names], miss, 200 + i
            ),
        }
        for i, dim in enumerate(dimension_names)
    }
    saturation = {}
    families = sorted({f for n in names for f in groups[n]["findings_by_family"]})
    for family in families:
        fired = [n for n in names if family in groups[n]["findings_by_family"]]
        key = next((k for k in RULE_TYPES if family.startswith(k)), family)
        saturation[family] = {
            "groups_evaluated": len(names),
            "groups_flagged": len(fired),
            "flagging_rate": len(fired) / len(names),
            "rule_type": RULE_TYPES.get(key, "not classified"),
            "findings_per_flagged_group": statistics.median(
                groups[n]["findings_by_family"][family]["findings"] for n in fired
            ),
        }
    return {
        "status": "completed",
        "experiment": EXPERIMENT_NAME,
        "data_origin": "benchmark",
        "metrics": {
            "design": {
                "source_experiment": "EXP-X02 (satsa-external-itsm-v1)",
                "unit": "assignment group",
                "groups": len(names),
                "detectors_thresholds_weights_changed": False,
                "note": "diagnostic only; no tuning on the evaluation data",
            },
            "construct_validity": CONSTRUCTS,
            "detector_saturation": saturation,
            "risk": {
                "distinct_total_values": len(set(risk)),
                "total_range": [min(risk), max(risk)],
                "total_median": statistics.median(risk),
                "total_vs_incident_volume": assoc(
                    risk, [groups[n]["prevalence"]["incidents"] for n in names], 300
                ),
                "dimensions": dimensions,
            },
            "prevalence_vs_sla_miss": prevalence_vs_sla,
            "prevalence_vs_risk": prevalence_vs_risk,
            "label_and_temporal_checks": _label_checks(
                source_csv, {n.replace("_", " ") for n in names}
            ),
            "groups": {
                n: {**groups[n], "sla_miss_rate": miss[i]} for i, n in enumerate(names)
            },
        },
        "performance": {
            "measurement_scope": "local synchronous legacy SQLite path",
            "total_elapsed_seconds": round(time.perf_counter() - started, 3),
        },
        "limitations": [
            "Diagnostic analysis of one external dataset; associations are descriptive.",
            "Rule-type and construct classifications are read from code and the adapter mapping.",
        ],
    }

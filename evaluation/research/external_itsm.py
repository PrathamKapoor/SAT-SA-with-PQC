"""External-data evaluation on a real IT incident-management event log.

Dataset: UCI "Incident management process enriched event log" (DOI
10.24432/C57S4H, CC BY 4.0), mapped by
``public_benchmarks.itsm_incident_log.adapter``. It is real operational
workflow data from an IT service desk, not a SOC; results are partial
external evidence about SAT-SA's workflow analytics, not SOC validation.

Questions (declared before execution):

* EXT-1 — feasibility: does the real log ingest and analyze through the
  unchanged SAT-SA pipeline, and what is lost in mapping?
* EXT-2 — detector behaviour on real data: which finding families fire, for
  how many entities (assignment groups)?
* EXT-3 — external association: does SAT-SA's entity risk/priority align
  with an independent operational outcome, the group's SLA-miss rate
  (``made_sla`` recorded by the source organisation), compared with
  data-only baselines on the same universe and top-k budget?

SAT-SA never sees the SLA labels: they are loaded only after its ranking is
computed. The relevant set for top-k metrics is the top quartile of groups
by SLA-miss rate. No directional hypothesis is claimed: SAT-SA's detectors
target supervisory execution gaps, not timeliness against an SLA.
"""

from __future__ import annotations

import json
import random
import statistics
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from evaluation.research.prioritization import ranking_metrics
from evaluation.research.statistics import bootstrap_interval, describe

EXPERIMENT_NAME = "satsa-external-itsm-v1"
K_PERCENTAGES = (10, 20, 30)


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def spearman(x: list[float], y: list[float]) -> float | None:
    """Spearman rank correlation with average ranks for ties."""
    if len(x) != len(y) or len(x) < 3:
        return None
    rx, ry = _ranks(x), _ranks(y)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    if not sxx or not syy:
        return None
    return sxy / (sxx * syy) ** 0.5


def _spearman_interval(x: list[float], y: list[float], seed: int) -> dict | None:
    indices = list(range(len(x)))

    def statistic(sample: Sequence[float]) -> float:
        picked = [int(i) for i in sample]
        value = spearman([x[i] for i in picked], [y[i] for i in picked])
        return value if value is not None else 0.0

    return bootstrap_interval(indices, statistic, seed=seed, resamples=2000)


def _ingest_counts(categories: dict[str, Any]) -> dict[str, dict[str, int]]:
    return {
        name: {
            key: int(summary.get(key, 0))
            for key in ("received", "accepted", "rejected")
        }
        for name, summary in sorted(categories.items())
        if isinstance(summary, dict)
    }


def _group_features(engine, entity_id: str) -> dict[str, float]:
    alerts = engine.query_all(
        "SELECT created_at,closed_at FROM satsa_alerts WHERE entity_id=?",
        (entity_id,),
    )
    resolution = [
        float(a["closed_at"]) - float(a["created_at"])
        for a in alerts
        if a["closed_at"] is not None
    ]
    escalations = engine.query_one(
        "SELECT COUNT(*) AS n FROM satsa_escalations WHERE entity_id=?",
        (entity_id,),
    )
    return {
        "incidents": float(len(alerts)),
        "median_resolution_seconds": statistics.median(resolution)
        if resolution
        else 0.0,
        "reassignments_per_incident": (escalations["n"] if escalations else 0)
        / max(1, len(alerts)),
    }


def run_external_itsm_experiment(
    scratch_dir: Path,
    *,
    source_csv: Path,
    expected_source_sha256: str | None = None,
    min_incidents: int = 30,
    seed: int = 0,
    random_trials: int = 1000,
) -> dict[str, Any]:
    from evaluation.ablation.runner import _emitted_families
    from public_benchmarks.itsm_incident_log.adapter import (
        build_submissions,
        sha256_file,
    )
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    from satsa.analysis.prioritize import prioritize_entities
    from satsa.analysis.risk import compute_entity_risk
    from satsa.service import SatsaService

    source_csv = Path(source_csv)
    actual = sha256_file(source_csv)
    if expected_source_sha256 and actual != expected_source_sha256:
        raise ValueError("source file checksum does not match the recorded download")
    root = Path(scratch_dir)
    root.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    report = build_submissions(
        source_csv, root / "derived", min_incidents=min_incidents
    )
    period = report["assessment_period"]
    submissions = sorted((root / "derived" / "submissions").iterdir())
    engine = SQLiteDatabaseEngine(root / "external.sqlite3")
    engine.connect()
    try:
        MigrationRunner(engine).migrate()
        service = SatsaService(engine)
        entities: dict[str, dict[str, Any]] = {}
        for directory in submissions:
            entity = service.register_entity(
                directory.name,
                sector="itsm-public-dataset",
                environment_class="uci-498",
            )
            assessment = service.open_assessment(
                entity.id, period["start"], period["end"]
            )
            ingest_started = time.perf_counter()
            ingest = service.submit(assessment.id, directory)
            entities[directory.name] = {
                "entity_id": entity.id,
                "assessment_id": assessment.id,
                "ingest_status": ingest.status,
                # IngestionResult has no "totals" key (the X02 run recorded
                # null here); per-category received/accepted/rejected
                # counts come from the category summaries.
                "ingest_counts": _ingest_counts(ingest.categories),
                "ingest_seconds": round(time.perf_counter() - ingest_started, 4),
            }
        # Analyze only after every group is ingested, so peer baselines see
        # the whole cohort for every entity.
        for name, info in entities.items():
            analysis_started = time.perf_counter()
            run = service.run_analysis(info["entity_id"], info["assessment_id"])
            info["run_status"] = run.status
            info["analysis_seconds"] = round(time.perf_counter() - analysis_started, 4)
            info["families"] = sorted(_emitted_families(engine, run.run_id))
            info["risk_total_score"] = round(
                compute_entity_risk(
                    engine, info["entity_id"], run_id=run.run_id
                ).total_score,
                4,
            )
            info["features"] = _group_features(engine, info["entity_id"])
        ranking = [
            item.entity_id
            for item in prioritize_entities(engine)
            if item.entity_id in {i["entity_id"] for i in entities.values()}
        ]
    finally:
        engine.close()

    # Labels are loaded only now, after SAT-SA's ranking exists.
    labels = json.loads((root / "derived" / "labels.json").read_text(encoding="utf-8"))
    names = sorted(entities)
    miss = {
        name: labels["groups"][name.replace("_", " ")]["sla_miss_rate"]
        for name in names
    }
    by_id = {entities[n]["entity_id"]: n for n in names}
    quartile = sorted(miss.values(), reverse=True)[max(0, len(names) // 4 - 1)]
    relevant = {entities[n]["entity_id"] for n in names if miss[n] >= quartile}

    rng = random.Random(f"{EXPERIMENT_NAME}:{seed}")
    tiebreak = {entities[n]["entity_id"]: rng.random() for n in names}

    def order_by(score: dict[str, float]) -> list[str]:
        return sorted(
            (entities[n]["entity_id"] for n in names),
            key=lambda e: (-score[by_id[e]], tiebreak[e]),
        )

    scores = {
        "incident_volume": {n: entities[n]["features"]["incidents"] for n in names},
        "slowest_median_resolution": {
            n: entities[n]["features"]["median_resolution_seconds"] for n in names
        },
        "reassignment_rate": {
            n: entities[n]["features"]["reassignments_per_incident"] for n in names
        },
        "satsa_risk_score": {n: entities[n]["risk_total_score"] for n in names},
    }
    methods = {
        "satsa_priority": ranking_metrics(
            ranking, relevant, k_percentages=K_PERCENTAGES
        ),
        **{
            name: ranking_metrics(
                order_by(score), relevant, k_percentages=K_PERCENTAGES
            )
            for name, score in scores.items()
            if name != "satsa_risk_score"
        },
    }
    random_samples = []
    for _ in range(random_trials):
        order = [entities[n]["entity_id"] for n in names]
        rng.shuffle(order)
        random_samples.append(
            ranking_metrics(order, relevant, k_percentages=K_PERCENTAGES)
        )
    methods["random"] = {
        str(k): {
            metric: statistics.fmean(s[str(k)][metric] for s in random_samples)
            for metric in ("precision", "recall", "ndcg")
        }
        | {"top_n": random_samples[0][str(k)]["top_n"]}
        for k in K_PERCENTAGES
    }
    y = [miss[n] for n in names]
    association = {}
    for index, (name, score) in enumerate(scores.items()):
        x = [score[n] for n in names]
        association[name] = {
            "spearman_rho": spearman(x, y),
            "bootstrap_interval": _spearman_interval(x, y, seed + index),
        }
    family_counts: dict[str, int] = {}
    for n in names:
        for family in entities[n]["families"]:
            family_counts[family] = family_counts.get(family, 0) + 1
    return {
        "status": "completed",
        "experiment": EXPERIMENT_NAME,
        "data_origin": "benchmark",
        "metrics": {
            "design": {
                "unit": "assignment group (entity) within one real organisation",
                "entities": len(names),
                "label": "SLA-miss rate from the source's final made_sla flag",
                "relevant_set": f"top quartile by SLA-miss rate (>= {quartile:.4f}), "
                f"{len(relevant)} groups",
                "k_percentages": list(K_PERCENTAGES),
                "random_trials": random_trials,
                "hypothesis": "none directional; exploratory external association",
            },
            "feasibility": {
                "transformation": report,
                "ingest_status_counts": {
                    status: sum(e["ingest_status"] == status for e in entities.values())
                    for status in {e["ingest_status"] for e in entities.values()}
                },
                "run_status_counts": {
                    status: sum(e["run_status"] == status for e in entities.values())
                    for status in {e["run_status"] for e in entities.values()}
                },
                "ingest_row_totals": {
                    key: sum(
                        counts[key]
                        for e in entities.values()
                        for counts in e["ingest_counts"].values()
                    )
                    for key in ("received", "accepted", "rejected")
                },
                "analysis_seconds": describe(
                    [e["analysis_seconds"] for e in entities.values()], unit="s"
                ),
            },
            "detector_behaviour": {
                "entities_emitting_family": dict(sorted(family_counts.items())),
                "not_evaluable": {
                    "coverage_gap and negative_space.missing_monitoring": "no assets "
                    "mapped (cmdb_ci known for 54 of 24,918 incidents)",
                    "escalation-based detectors": "escalations are reassignment "
                    "proxies, not severity escalations",
                    "dispositions": "closure codes are anonymized; every outcome "
                    "is 'other'",
                },
            },
            "association_with_sla_miss_rate": association,
            "ranking_vs_sla_miss_quartile": methods,
            "entities": {n: {**entities[n], "sla_miss_rate": miss[n]} for n in names},
        },
        "performance": {
            "measurement_scope": "local synchronous legacy SQLite path",
            "total_elapsed_seconds": round(time.perf_counter() - started, 3),
        },
        "limitations": [
            "IT service-management tickets, not SOC security workflow; domain transfer is untested.",
            "One organisation, one period, 50 groups: associations are descriptive with bootstrap intervals over groups.",
            "SLA miss is an operational timeliness outcome, not a label of supervisory execution quality.",
            "Reassignments are used as escalation proxies and closure codes are anonymized.",
            "Timestamps have no time zone and are interpreted as UTC.",
        ],
    }

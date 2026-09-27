"""Reproducible figure-source data from verified experiment bundles.

No plots are drawn. Each candidate figure gets a CSV of source values and an
entry in ``figures-index.json`` giving the figure id, experiment, axes,
units, aggregation, sample size and source bundle, so a later phase can draw
figures without reading the code. Bundles are verified before use.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from evaluation.research.tables import BundleIntegrityError, load_bundle


def _write(out: Path, name: str, rows: list[dict[str, Any]]) -> Path:
    path = out / f"{name}.csv"
    columns = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _prioritization(results: dict[str, Any]) -> tuple[list[dict], dict]:
    rows = []
    for replicate in results["metrics"]["replicates"]:
        for method, values in replicate["methods"].items():
            for k in (10, 20, 30):
                rows.append(
                    {
                        "seed": replicate["seed"],
                        "method": method,
                        "k_percent": k,
                        "recall": values[str(k)]["recall"],
                        "ndcg": values[str(k)]["ndcg"],
                    }
                )
    meta = {
        "x": "top-k budget (percent of entities)",
        "y": "recall@k and NDCG@k",
        "units": "fraction",
        "series": "method",
        "aggregation": "one row per population seed; plot medians with per-seed points",
        "sample_size": len(results["metrics"]["replicates"]),
    }
    return rows, meta


def _ablation(results: dict[str, Any]) -> tuple[list[dict], dict]:
    level = results["metrics"]["scenario_level"]
    full = level["full"]["micro"]
    rows = [
        {
            "worker_removed": "(none)",
            "precision": full["precision"],
            "recall": full["recall"],
            "f1": full["f1"],
        }
    ]
    rows += [
        {
            "worker_removed": w["worker_removed"],
            "precision": w["micro"]["precision"],
            "recall": w["micro"]["recall"],
            "f1": w["micro"]["f1"],
        }
        for w in level["workers"]
    ]
    meta = {
        "x": "worker removed",
        "y": "micro precision / recall / F1 against catalog labels",
        "units": "fraction",
        "aggregation": "micro over 5 catalog scenarios",
        "sample_size": 5,
    }
    return rows, meta


def _peer(results: dict[str, Any]) -> tuple[list[dict], dict]:
    rows = [
        {
            "spread": r["spread"],
            "cohort_size": r["cohort_size"],
            "subject_closure_seconds": r["subject_closure_seconds"],
            "deviation_mad_units": r["deviation_mad_units"],
            "finding_emitted": r["finding_emitted"],
            "subject_priority_rank": r["subject_priority_rank"],
        }
        for r in results["metrics"]["matrix"]
    ]
    meta = {
        "x": "subject closure value",
        "y": "finding emitted / deviation in MAD units",
        "units": "seconds; MAD units",
        "series": "cohort size, facet by spread",
        "aggregation": "none (one deterministic cell each)",
        "sample_size": len(rows),
    }
    return rows, meta


def _robustness(results: dict[str, Any]) -> tuple[list[dict], dict]:
    rows = []
    for key, v in results["metrics"]["record_omission_by_rate"].items():
        kind, rate = key.split(":")
        rows.append(
            {
                "omission": kind,
                "rate": float(rate),
                "replicates": v["replicates"],
                "rejected_fraction": v["rejected_by_validation"] / v["replicates"],
                "family_set_changed_fraction": v["family_set_changed"]
                / v["replicates"],
            }
        )
    meta = {
        "x": "record omission rate",
        "y": "fraction of replicates rejected / with changed finding families",
        "units": "fraction",
        "series": "independent vs cascade omission",
        "aggregation": "count over 5 scenarios x 5 seeds",
        "sample_size": 25,
    }
    return rows, meta


def _orchestration(results: dict[str, Any]) -> tuple[list[dict], dict]:
    rows = [
        {
            "trial": t["trial"],
            "mode": t["mode"],
            "processing_seconds": t["processing_seconds"],
            "db_operations_total": t["db_operations_total"],
            "trust_finalization_seconds": t["stage_seconds"].get("trust_finalization"),
        }
        for t in results["metrics"]["trials"]
    ]
    meta = {
        "x": "execution mode",
        "y": "processing time excluding the human decision",
        "units": "seconds",
        "aggregation": "per-trial values; plot distribution (box) with median",
        "sample_size": results["metrics"]["design"]["trials_per_mode"],
    }
    return rows, meta


def _recovery(results: dict[str, Any]) -> tuple[list[dict], dict]:
    rows = [
        {
            "mode": t["mode"],
            "interruption_point": t["point"],
            "trial": t["trial"],
            "recovered": t["recovered_to_completion"],
            "recovery_seconds": t["recovery_seconds"],
        }
        for t in results["metrics"]["trials"]
    ]
    meta = {
        "x": "interruption point",
        "y": "recovery latency",
        "units": "seconds",
        "series": "mode",
        "aggregation": "per-trial values",
        "sample_size": len(rows),
    }
    return rows, meta


def _external(results: dict[str, Any]) -> tuple[list[dict], dict]:
    rows = [
        {
            "group": name,
            "sla_miss_rate": e["sla_miss_rate"],
            "satsa_risk_total_score": e["risk_total_score"],
            "incidents": e["features"]["incidents"],
            "median_resolution_seconds": e["features"]["median_resolution_seconds"],
        }
        for name, e in sorted(results["metrics"]["entities"].items())
    ]
    meta = {
        "x": "SAT-SA entity risk score",
        "y": "SLA-miss rate recorded by the source organisation",
        "units": "score; fraction",
        "aggregation": "one point per assignment group",
        "sample_size": len(rows),
    }
    return rows, meta


def _trust_overhead(results: dict[str, Any]) -> tuple[list[dict], dict]:
    rows = [
        {
            "trial": t["trial"],
            "mode": t["mode"],
            "finalization_seconds": t["stage_seconds"].get("trust_finalization"),
            "run_attestation_seconds": t["stage_seconds"].get("trust_run_attestation"),
            "verification_seconds": t["trust_verification_seconds"],
        }
        for t in results["metrics"]["trials"]
        if t["mode"] in {"direct", "graph"}
    ]
    meta = {
        "x": "execution mode",
        "y": "TRUST-SAT finalization, attestation and verification time",
        "units": "seconds",
        "aggregation": "per-trial values",
        "sample_size": results["metrics"]["design"]["trials_per_mode"],
    }
    return rows, meta


def _failure(results: dict[str, Any]) -> tuple[list[dict], dict]:
    rows = [
        {
            "group": name,
            "sla_miss_rate": g["sla_miss_rate"],
            "fast_closure_rate": g["prevalence"]["fast_closure_rate"],
            "cases_without_steps_rate": g["prevalence"]["cases_without_steps_rate"],
            "execution_gap_dimension": g["risk_dimensions"]["execution_gap"],
            "risk_total": g["risk_total"],
        }
        for name, g in sorted(results["metrics"]["groups"].items())
    ]
    meta = {
        "x": "fast-closure prevalence (detector input condition)",
        "y": "SLA-miss rate; execution-gap risk dimension",
        "units": "fraction; score",
        "aggregation": "one point per assignment group",
        "sample_size": len(rows),
    }
    return rows, meta


FIGURES = {
    "FIG-6c-trust-overhead": ("satsa-orchestration-overhead-v1", _trust_overhead),
    "FIG-8-external-construct-inversion": (
        "satsa-external-itsm-failure-analysis-v1",
        _failure,
    ),
    "FIG-2-prioritization": ("satsa-prioritization-replicated-v1", _prioritization),
    "FIG-3-ablation": ("satsa-component-ablation-v1", _ablation),
    "FIG-4-peer-sensitivity": ("peer-cohort-sweep-v1", _peer),
    "FIG-5-missing-evidence-robustness": (
        "satsa-evidence-perturbation-v1",
        _robustness,
    ),
    "FIG-6a-langgraph-overhead": ("satsa-orchestration-overhead-v1", _orchestration),
    "FIG-6b-recovery": ("satsa-orchestration-recovery-v1", _recovery),
    "FIG-7-external-risk-vs-sla": ("satsa-external-itsm-v1", _external),
}


def export_figures(
    bundles: list[Path],
    out: Path,
    *,
    expected_manifests: dict[str, str] | None = None,
) -> dict[str, Any]:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    loaded: dict[str, tuple[Path, dict[str, Any]]] = {}
    skipped = []
    for bundle in sorted(bundles):
        try:
            _manifest, results = load_bundle(
                bundle,
                expected_manifest_sha256=(expected_manifests or {}).get(bundle.name),
            )
        except (BundleIntegrityError, FileNotFoundError, KeyError) as exc:
            skipped.append({"bundle": bundle.name, "reason": str(exc)})
            continue
        experiment = results.get("experiment") or results.get("benchmark_name", "")
        loaded.setdefault(experiment, (bundle, results))
    index = {"figures": [], "skipped": skipped}
    for figure_id, (experiment, builder) in FIGURES.items():
        if experiment not in loaded:
            index["figures"].append(
                {
                    "figure_id": figure_id,
                    "experiment": experiment,
                    "status": "no source bundle",
                }
            )
            continue
        bundle, results = loaded[experiment]
        rows, meta = builder(results)
        path = _write(out, figure_id, rows)
        index["figures"].append(
            {
                "figure_id": figure_id,
                "experiment": experiment,
                "source_bundle": bundle.name,
                "data_file": path.name,
                "data_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                **meta,
            }
        )
    (out / "figures-index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return index

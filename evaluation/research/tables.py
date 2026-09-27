"""Deterministic paper-table export from completed experiment bundles.

Tables are regenerated from ``raw/results.json`` of completed bundles only,
after re-checking every artifact hash recorded in the bundle manifest; a
bundle whose files no longer match its manifest is refused. Each table is
written as CSV, Markdown and LaTeX, and a ``tables-manifest.json`` records
the source bundle, its commit and the output file hashes. Bundles are never
modified.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

Row = dict[str, Any]


class BundleIntegrityError(RuntimeError):
    pass


def load_bundle(
    path: Path, *, expected_manifest_sha256: str | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (manifest, raw results) after verifying recorded hashes."""
    manifest_bytes = (path / "manifest.json").read_bytes()
    if (
        expected_manifest_sha256
        and hashlib.sha256(manifest_bytes).hexdigest() != expected_manifest_sha256
    ):
        raise BundleIntegrityError(f"{path.name}: manifest differs from the freeze")
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    if manifest.get("status") != "completed":
        raise BundleIntegrityError(f"{path.name}: bundle is not completed")
    for relative, expected in manifest.get("artifacts_sha256", {}).items():
        actual = hashlib.sha256((path / relative).read_bytes()).hexdigest()
        if actual != expected:
            raise BundleIntegrityError(f"{path.name}: {relative} hash mismatch")
    results = json.loads((path / "raw" / "results.json").read_text(encoding="utf-8"))
    return manifest, results


def _robustness(results: dict[str, Any]) -> dict[str, list[Row]]:
    metrics = results["metrics"]
    families = [
        {
            "family": name,
            "conditions": v["conditions"],
            "valid": v["validation_status_counts"].get("valid", 0),
            "invalid": v["validation_status_counts"].get("invalid", 0),
            "matches_expected": v["matches_expected"],
            "no_expectation": v["no_declared_expectation"],
            "analysed": v["completed_analyses"],
            "family_set_changed": v["family_set_changed_vs_control"],
            "withheld_findings": v.get("withheld_invalid_findings"),
        }
        for name, v in sorted(
            metrics["validation_contract_conformance"]["by_family"].items()
        )
    ]
    omission = [
        {
            "condition": key,
            "replicates": v["replicates"],
            "rejected": v["rejected_by_validation"],
            "analysed": v["completed_analyses"],
            "family_set_changed": v["family_set_changed"],
            "mean_families_removed": v["families_removed_per_run"]["mean"],
            "mean_families_added": v["families_added_per_run"]["mean"],
        }
        for key, v in metrics["record_omission_by_rate"].items()
    ]
    return {"robustness_by_family": families, "robustness_omission": omission}


def _integrity(results: dict[str, Any]) -> dict[str, list[Row]]:
    return {
        "integrity_mutations": [
            {
                "mutation": m["mutation"],
                "target": m.get("target_object"),
                "expected": m.get("expected_verification_outcome", "tampered"),
                "outcome": m["verification_outcome"],
                "failure_category": m["failure_category"],
                "verification_ms": m["verification_ms"],
            }
            for m in results["mutations"]
        ]
    }


def _overhead(results: dict[str, Any]) -> dict[str, list[Row]]:
    per_mode = results["metrics"]["per_mode"]
    rows = []
    for mode, v in per_mode.items():
        rows.append(
            {
                "mode": mode,
                "n": v["processing_seconds"]["n"],
                "processing_median_s": v["processing_seconds"]["median"],
                "processing_p95_s": v["processing_seconds"]["p95"],
                "outside_domain_median_s": v["outside_domain_stages_seconds"]["median"],
                "db_calls_median": v["db_operations_total"]["median"],
                "checkpoints_median": (v["graph_checkpoints"] or {}).get("median"),
            }
        )
    comparisons = [
        {
            "comparison": name,
            "n_pairs": c["n_pairs"],
            "median_difference": c["median_difference"],
            "relative": c["relative_median_difference"],
            "ci_lower": (c["median_difference_interval"] or {}).get("lower"),
            "ci_upper": (c["median_difference_interval"] or {}).get("upper"),
        }
        for name, c in results["metrics"]["comparisons"].items()
    ]
    return {"orchestration_modes": rows, "orchestration_comparisons": comparisons}


def _recovery(results: dict[str, Any]) -> dict[str, list[Row]]:
    return {
        "recovery": [
            {
                "cell": cell,
                "trials": v["trials"],
                "recovered": v["recovered_to_completion"],
                "outputs_match": v["outputs_match_reference"],
                "trust_verified": v["trust_verified"],
                "repeated_completed_stages": v["runs_with_repeated_completed_stages"],
                "recovery_median_s": v["recovery_seconds"]["median"],
            }
            for cell, v in results["metrics"]["summary"].items()
        ]
    }


def _peer(results: dict[str, Any]) -> dict[str, list[Row]]:
    return {"peer_sweep": list(results["metrics"]["matrix"])}


def _ablation(results: dict[str, Any]) -> dict[str, list[Row]]:
    scenario = results["metrics"]["scenario_level"]
    full = scenario["full"]["micro"]
    tables = {
        "ablation_scenario": [
            {
                "worker_removed": "(none: full set)",
                **{k: full[k] for k in ("tp", "fp", "fn", "precision", "recall", "f1")},
            }
        ]
        + [
            {
                "worker_removed": w["worker_removed"],
                **{
                    k: w["micro"][k]
                    for k in ("tp", "fp", "fn", "precision", "recall", "f1")
                },
            }
            for w in scenario["workers"]
        ]
    }
    population = results["metrics"].get("population_level")
    if population:
        rows = []
        for w in population["workers"]:
            for metric, c in w["comparisons"].items():
                rows.append(
                    {
                        "worker_removed": w["worker_removed"],
                        "metric": metric,
                        "n_seeds": c["n_pairs"],
                        "full_mean": c["baseline"]["mean"],
                        "ablated_mean": c["treatment"]["mean"],
                        "median_difference": c["median_difference"],
                        "adequacy": c["adequacy"],
                    }
                )
        tables["ablation_population"] = rows
    return tables


def _prioritization(results: dict[str, Any]) -> dict[str, list[Row]]:
    summary = results["metrics"]["summary"]
    rows = [
        {
            "metric": metric,
            "method": method,
            "n": v["n"],
            "median": v["median"],
            "mean": v["mean"],
            "min": v["min"],
            "max": v["max"],
        }
        for metric, methods in summary.items()
        for method, v in methods.items()
    ]
    comparisons = [
        {
            "comparison": name,
            "n_pairs": c["n_pairs"],
            "median_difference": c["median_difference"],
            "ci_lower": (c["median_difference_interval"] or {}).get("lower"),
            "ci_upper": (c["median_difference_interval"] or {}).get("upper"),
            "satsa_greater_in_pairs": c["treatment_greater_in_pairs"],
        }
        for name, c in results["metrics"]["comparisons"].items()
    ]
    return {"prioritization": rows, "prioritization_comparisons": comparisons}


def _controlled(results: dict[str, Any]) -> dict[str, list[Row]]:
    metrics = results["metrics"]
    closure = metrics["closure_time_baselines"]
    baselines = [
        {
            "detector": name,
            "n_records": closure["n_records"],
            **{k: v[k] for k in ("tp", "fp", "fn", "tn", "precision", "recall", "f1")},
        }
        for name, v in sorted(closure["comparison"].items())
    ]
    scenarios = [
        {
            "scenario": s["case_id"],
            "expected": s["metrics"]["expected_families"],
            "emitted": s["metrics"]["emitted_families"],
            "tp": s["metrics"]["tp"],
            "fp": s["metrics"]["fp"],
            "fn": s["metrics"]["fn"],
            "action_ok": s["action"]["ok"],
        }
        for s in metrics["scenario_corpus"]["per_scenario"]
    ]
    return {"baseline_closure_time": baselines, "controlled_scenarios": scenarios}


def _external(results: dict[str, Any]) -> dict[str, list[Row]]:
    metrics = results["metrics"]
    association = [
        {
            "score": name,
            "spearman_rho": v["spearman_rho"],
            "ci_lower": (v["bootstrap_interval"] or {}).get("lower"),
            "ci_upper": (v["bootstrap_interval"] or {}).get("upper"),
            "n_groups": metrics["design"]["entities"],
        }
        for name, v in metrics["association_with_sla_miss_rate"].items()
    ]
    ranking = [
        {
            "method": method,
            **{
                f"{metric}@{k}%": v[str(k)][metric]
                for k in (10, 20, 30)
                for metric in ("precision", "recall", "ndcg")
            },
            "review_volume_to_find_all": v.get("review_volume_to_find_all"),
        }
        for method, v in metrics["ranking_vs_sla_miss_quartile"].items()
    ]
    families = [
        {
            "family": family,
            "groups_emitting": count,
            "of_groups": metrics["design"]["entities"],
        }
        for family, count in metrics["detector_behaviour"][
            "entities_emitting_family"
        ].items()
    ]
    return {
        "external_association": association,
        "external_ranking": ranking,
        "external_detector_saturation": families,
    }


BUILDERS: dict[str, Callable[[dict[str, Any]], dict[str, list[Row]]]] = {
    "satsa-controlled-supervisory-benchmark": _controlled,
    "satsa-external-itsm-v1": _external,
    "satsa-evidence-perturbation-v1": _robustness,
    "trust-sat-controlled-mutation-v1": _integrity,
    "satsa-orchestration-overhead-v1": _overhead,
    "satsa-orchestration-recovery-v1": _recovery,
    "peer-cohort-sweep-v1": _peer,
    "satsa-component-ablation-v1": _ablation,
    "satsa-prioritization-replicated-v1": _prioritization,
}


def _latex_escape(value: Any) -> str:
    text = "--" if value is None else str(value)
    for char, escaped in (
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
    ):
        text = text.replace(char, escaped)
    return text


def _cell(value: Any) -> str:
    if value is None:
        return "undefined"
    if isinstance(value, float):
        return f"{value:.4g}"
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def write_table(out: Path, name: str, rows: list[Row], source: str) -> list[Path]:
    columns = list(rows[0]) if rows else []
    paths = [out / f"{name}.csv", out / f"{name}.md", out / f"{name}.tex"]
    with paths[0].open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerows([[_cell(row.get(c)) for c in columns] for row in rows])
    md = [f"<!-- generated from bundle {source}; do not edit -->", ""]
    md.append("| " + " | ".join(columns) + " |")
    md.append("| " + " | ".join("---" for _ in columns) + " |")
    md.extend(
        "| " + " | ".join(_cell(row.get(c)).replace("|", "\\|") for c in columns) + " |"
        for row in rows
    )
    paths[1].write_text("\n".join(md) + "\n", encoding="utf-8")
    tex = [
        f"% generated from bundle {source}; do not edit",
        r"\begin{tabular}{" + "l" * len(columns) + "}",
        r"\hline",
        " & ".join(_latex_escape(c) for c in columns) + r" \\",
        r"\hline",
    ]
    tex.extend(
        " & ".join(_latex_escape(_cell(row.get(c))) for c in columns) + r" \\"
        for row in rows
    )
    tex += [r"\hline", r"\end{tabular}"]
    paths[2].write_text("\n".join(tex) + "\n", encoding="utf-8")
    return paths


def export_tables(
    bundles: list[Path],
    out: Path,
    *,
    expected_manifests: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Export tables; ``expected_manifests`` (bundle name -> manifest
    SHA-256, e.g. from a freeze) also rejects edited manifests."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {"sources": [], "tables": {}, "skipped": []}
    used: set[str] = set()
    for bundle in sorted(bundles):
        try:
            manifest, results = load_bundle(
                bundle,
                expected_manifest_sha256=(expected_manifests or {}).get(bundle.name),
            )
        except (BundleIntegrityError, FileNotFoundError, KeyError) as exc:
            record["skipped"].append({"bundle": bundle.name, "reason": str(exc)})
            continue
        experiment = results.get("experiment") or results.get("benchmark_name", "")
        builder = BUILDERS.get(experiment)
        if builder is None:
            record["skipped"].append(
                {"bundle": bundle.name, "reason": "no table builder for experiment"}
            )
            continue
        record["sources"].append(
            {
                "bundle": bundle.name,
                "experiment": experiment,
                "commit": manifest["code"]["commit"],
                "source_tree_dirty": manifest["code"]["source_tree_dirty"],
                "results_sha256": manifest["artifacts_sha256"]["raw/results.json"],
            }
        )
        for name, rows in builder(results).items():
            if name in used:
                # Two bundles of one experiment: keep both, never overwrite.
                name = f"{name}__{bundle.name}"
            used.add(name)
            for path in write_table(out, name, rows, bundle.name):
                record["tables"][path.name] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
    (out / "tables-manifest.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return record

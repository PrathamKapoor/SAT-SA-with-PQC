"""Statistical audit of canonical experiment bundles.

Every row is read from a bundle (no typed numbers) and states the sample
size, what the *independent* unit actually is, how many repeated or derived
observations sit inside it, the estimate, the interval if one exists, and the
number of comparisons made. The audit deliberately separates trial counts
from independent-sample counts: repeated runs on one machine, perturbations of
the same fixtures and cells of an engineered grid are not independent samples
of a population. No inferential tests are run.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Row = dict[str, Any]


def _interval(c: dict[str, Any] | None) -> list[Any] | None:
    if not c:
        return None
    return [c.get("lower"), c.get("upper")]


def _controlled(r: dict[str, Any]) -> list[Row]:
    m = r["metrics"]
    micro = m["scenario_corpus"]["micro"]
    closure = m["closure_time_baselines"]
    prio = m["prioritization"]
    return [
        {
            "metric": "micro family precision / recall / F1",
            "n": m["scenario_corpus"]["coverage"]["executed"],
            "independent_unit": "authored catalog scenario",
            "repeated_or_derived": f"{micro['tp'] + micro['fp'] + micro['fn']} scenario-family pairs",
            "estimate": {k: micro[k] for k in ("precision", "recall", "f1")},
            "interval": None,
            "comparisons": 0,
            "adequacy": "descriptive: 5 authored scenarios",
        },
        {
            "metric": "closure-time detector F1 vs 5 baselines",
            "n": closure["n_records"],
            "independent_unit": "construction-labelled closure record",
            "repeated_or_derived": "none",
            "estimate": {k: v["f1"] for k, v in closure["comparison"].items()},
            "interval": None,
            "comparisons": len(closure["comparison"]) - 1,
            "adequacy": "descriptive: 12 records, 3 positive",
        },
        {
            "metric": "recall@k vs random order",
            "n": 1,
            "independent_unit": "generated population",
            "repeated_or_derived": f"{prio['n_random_trials']} random permutations (comparator distribution, not replications)",
            "estimate": prio["satsa_recall_at_k"],
            "interval": None,
            "comparisons": len(prio["satsa_recall_at_k"]),
            "adequacy": "single population; superseded in scope by EXP-PR01",
        },
    ]


def _robustness(r: dict[str, Any]) -> list[Row]:
    m = r["metrics"]
    conformance = m["validation_contract_conformance"]
    return [
        {
            "metric": "validation matches declared contract",
            "n": conformance["conditions_with_expectation"],
            "independent_unit": "authored fixture (5); conditions are perturbations of them",
            "repeated_or_derived": "declared perturbation conditions",
            "estimate": conformance["matches"],
            "interval": None,
            "comparisons": 0,
            "adequacy": "conformance count, not a rate estimate for real data",
        },
        *[
            {
                "metric": f"omission {key}: rejected / family set changed",
                "n": v["replicates"],
                "independent_unit": "fixture x omission seed (seeds vary which records are removed)",
                "repeated_or_derived": "5 scenarios x 5 seeds",
                "estimate": {
                    "rejected": v["rejected_by_validation"],
                    "family_set_changed": v["family_set_changed"],
                },
                "interval": None,
                "comparisons": 0,
                "adequacy": "descriptive counts",
            }
            for key, v in m["record_omission_by_rate"].items()
        ],
    ]


def _overhead(r: dict[str, Any]) -> list[Row]:
    m = r["metrics"]
    rows = []
    for name, c in m["comparisons"].items():
        rows.append(
            {
                "metric": name,
                "n": c["n_pairs"],
                "independent_unit": "none beyond one machine: repeated workflow runs",
                "repeated_or_derived": "paired by trial index; rotated mode order",
                "estimate": c["median_difference"],
                "interval": _interval(c["median_difference_interval"]),
                "comparisons": len(m["comparisons"]),
                "adequacy": "describes run-to-run variability on this machine only",
            }
        )
    return rows


def _recovery(r: dict[str, Any]) -> list[Row]:
    s = r["metrics"]["summary"]
    return [
        {
            "metric": "recovered with identical outputs",
            "n": sum(v["trials"] for v in s.values()),
            "independent_unit": "injected interruption run (6 points x 2 modes x 3 trials)",
            "repeated_or_derived": "3 deterministic repeats per cell",
            "estimate": sum(v["outputs_match_reference"] for v in s.values()),
            "interval": None,
            "comparisons": 0,
            "adequacy": "mechanism check; not a failure-rate estimate",
        }
    ]


def _integrity(r: dict[str, Any]) -> list[Row]:
    s = r["mutation_summary"]
    return [
        {
            "metric": "mutations detected / expected tampered",
            "n": s["tested"],
            "independent_unit": "one finalized workflow; mutation class is the condition",
            "repeated_or_derived": "one mutation per class",
            "estimate": f"{s['detected_of_expected_tampered']}/{s['expected_tampered']}",
            "interval": None,
            "comparisons": 0,
            "adequacy": "not a detection-rate estimate",
        }
    ]


def _peer(r: dict[str, Any]) -> list[Row]:
    matrix = r["metrics"]["matrix"]
    return [
        {
            "metric": "peer finding emitted",
            "n": len(matrix),
            "independent_unit": "engineered deterministic cell",
            "repeated_or_derived": "factorial grid",
            "estimate": sum(row["finding_emitted"] for row in matrix),
            "interval": None,
            "comparisons": 0,
            "adequacy": "mechanism map, not a population sample",
        }
    ]


def _ablation(r: dict[str, Any]) -> list[Row]:
    m = r["metrics"]
    rows = [
        {
            "metric": "scenario micro recall with one worker removed",
            "n": 5,
            "independent_unit": "authored catalog scenario",
            "repeated_or_derived": f"{len(m['scenario_level']['workers'])} ablated worker sets",
            "estimate": {
                w["worker_removed"]: w["micro"]["recall"]
                for w in m["scenario_level"]["workers"]
            },
            "interval": None,
            "comparisons": len(m["scenario_level"]["workers"]),
            "adequacy": "descriptive",
        }
    ]
    population = m.get("population_level")
    if population:
        rows.append(
            {
                "metric": f"population recall@{population['k_percent']}% change",
                "n": len(population["seeds"]),
                "independent_unit": "generated population (seed)",
                "repeated_or_derived": "paired full vs ablated per seed",
                "estimate": {
                    w["worker_removed"]: w["comparisons"][
                        f"recall@{population['k_percent']}%"
                    ]["median_difference"]
                    for w in population["workers"]
                },
                "interval": None,
                "comparisons": 3 * len(population["workers"]),
                "adequacy": "exploratory (n < 10; no intervals)",
            }
        )
    return rows


def _prioritization(r: dict[str, Any]) -> list[Row]:
    m = r["metrics"]
    rows = []
    for name, c in m["comparisons"].items():
        if "@20%" not in name:
            continue
        rows.append(
            {
                "metric": name,
                "n": c["n_pairs"],
                "independent_unit": "generated population (seed)",
                "repeated_or_derived": "random baseline = mean of 200 permutations per seed",
                "estimate": c["median_difference"],
                "interval": _interval(c["median_difference_interval"]),
                "comparisons": len(m["comparisons"]),
                "adequacy": "descriptive; uncorrected across comparisons",
            }
        )
    return rows


def _external(r: dict[str, Any]) -> list[Row]:
    m = r["metrics"]
    return [
        {
            "metric": f"Spearman rho ({name}) vs SLA-miss rate",
            "n": m["design"]["entities"],
            "independent_unit": "assignment group within one organisation (not independent organisations)",
            "repeated_or_derived": "group-level aggregates of incidents",
            "estimate": v["spearman_rho"],
            "interval": _interval(v["bootstrap_interval"]),
            "comparisons": len(m["association_with_sla_miss_rate"]),
            "adequacy": "descriptive; one external dataset",
        }
        for name, v in m["association_with_sla_miss_rate"].items()
    ]


def _failure(r: dict[str, Any]) -> list[Row]:
    m = r["metrics"]
    return [
        {
            "metric": f"Spearman rho ({name}) vs SLA-miss rate",
            "n": m["design"]["groups"],
            "independent_unit": "assignment group within one organisation",
            "repeated_or_derived": "diagnostic prevalence metric",
            "estimate": v["spearman_rho"],
            "interval": _interval(v["bootstrap_interval"]),
            "comparisons": len(m["prevalence_vs_sla_miss"])
            + len(m["prevalence_vs_risk"]),
            "adequacy": "diagnostic; used to explain X02b, not as a claim of effect",
        }
        for name, v in m["prevalence_vs_sla_miss"].items()
    ]


AUDITORS: dict[str, Callable[[dict[str, Any]], list[Row]]] = {
    "satsa-controlled-supervisory-benchmark": _controlled,
    "satsa-evidence-perturbation-v1": _robustness,
    "satsa-orchestration-overhead-v1": _overhead,
    "satsa-orchestration-recovery-v1": _recovery,
    "trust-sat-controlled-mutation-v1": _integrity,
    "peer-cohort-sweep-v1": _peer,
    "satsa-component-ablation-v1": _ablation,
    "satsa-prioritization-replicated-v1": _prioritization,
    "satsa-external-itsm-v1": _external,
    "satsa-external-itsm-failure-analysis-v1": _failure,
}


def audit_bundle(bundle_name: str, results: dict[str, Any]) -> list[Row]:
    experiment = results.get("experiment") or results.get("benchmark_name", "")
    auditor = AUDITORS.get(experiment)
    if auditor is None:
        return []
    return [
        {"bundle": bundle_name, "experiment": experiment, **row}
        for row in auditor(results)
    ]

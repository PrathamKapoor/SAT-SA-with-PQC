"""Controlled supervisory benchmark — versioned manifest.

The manifest declares, *before* any pipeline run, exactly what the
controlled benchmark measures, which ground-truth labels it uses, and
where those labels come from. It follows the project's standing
ground-truth rule: expected labels originate from the scenario
specification (``satsa.analysis.validate.synthetic_ground_truth``)
created independently of any detector output — never from what the
detectors flagged.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

from satsa import __version__ as SATSA_VERSION

BENCHMARK_NAME = "satsa-controlled-supervisory-benchmark"
BENCHMARK_VERSION = "1.0.0"

# The single authoritative label source. The runner asserts that this
# catalog is what actually drives scoring — labels are never derived
# from detector output (that would let SAT-SA grade itself).
GROUND_TRUTH_SOURCE = "satsa.analysis.validate.synthetic_ground_truth"

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Executable single-entity scenario builders live in
# satsa/analysis/compval.py::SCENARIO_MAP. Scenarios absent from that
# map are carried in the manifest with their honest not-executable
# reason (also from compval.py) — they are never fabricated as run.
SCENARIO_CORPUS_SOURCE = "satsa.analysis.compval.SCENARIO_MAP"

# No cross-detector side effect is asserted as permitted here. The
# ground-truth catalog declares expected signal families; it does NOT
# declare family exclusivity. Any emitted family outside the expected
# set is reported as a false positive at scenario level AND listed
# separately, so a reader can see exactly what fired beyond the label.
PERMITTED_SIDE_EFFECTS: dict[str, list[str]] = {}

LIMITATIONS = [
    "Synthetic/derived origin: every scenario is a deterministic, "
    "hand-built single-entity fixture or a seeded synthetic generator "
    "population. This benchmark is NOT real SOC/CSE/NCIIPC validation "
    "and is not equivalent to real SOC operations.",
    "Five catalog scenarios (anomaly-rate, peer-deviation, borderline, "
    "noisy, conflicting-evidence) cannot be produced deterministically "
    "in a single-entity fixture and are reported as not_executed with "
    "their documented reasons — never scored as zero.",
    "The catalog declares expected signal families; it does not assert "
    "family exclusivity, so emitted-but-unexpected families are counted "
    "as false positives and also reported separately as extra_families.",
    "Per-record precision/recall for negative-space, anomaly, peer "
    "benchmarking, drift, and case similarity is not computable: the "
    "scenario fixtures declare family-level and action-level labels "
    "only. No such metric is invented.",
    "The workload/prioritization section is a simulated measurement on "
    "synthetically-labeled entities ('simulated_workload_reduction') — "
    "never a claim about real analyst time saved.",
    "Baseline comparisons are statistical (z-score/MAD/IQR/fixed/"
    "random) on closure-time data whose labels are stated by "
    "construction; conclusions are limited to the controlled corpus.",
    "Ablation reports which finding families disappear when one worker "
    "is removed on this corpus scope; a worker with no unique loss here "
    "is not thereby useless (see evaluation/ablation/runner.py).",
]


def build_manifest(*, workload_seed: int = 42) -> dict:
    """Return the versioned benchmark manifest.

    Every value is either a declared constant, read from the
    authoritative ground-truth catalog, or a documented constant —
    nothing is read from detector output.
    """
    from satsa.analysis.compval import NOT_EXECUTABLE_REASON, SCENARIO_MAP
    from satsa.analysis.validate import synthetic_ground_truth

    catalog = synthetic_ground_truth()
    scenarios = []
    for case in catalog:
        executable = case.case_id in SCENARIO_MAP
        entry = {
            "case_id": case.case_id,
            "scenario": case.scenario,
            "description": case.description,
            "declared_expected_signals": sorted(case.expected_signals),
            "declared_expected_action": case.expected_action,
            "executable": executable,
            "ground_truth_origin": "declared scenario specification "
                                   "(catalog entry authored before any "
                                   "pipeline run; not derived from "
                                   "detector output)",
        }
        if executable:
            entry["generator"] = (
                f"satsa.analysis.compval.SCENARIO_MAP['{case.case_id}'] "
                "(deterministic fixture builder, no randomness)")
        else:
            entry["not_executable_reason"] = NOT_EXECUTABLE_REASON.get(
                case.case_id,
                "No deterministic single-entity fixture exists for this "
                "scenario; the runner refuses to fabricate one.")
        scenarios.append(entry)

    return {
        "benchmark_name": BENCHMARK_NAME,
        "benchmark_version": BENCHMARK_VERSION,
        "ground_truth_source": GROUND_TRUTH_SOURCE,
        "provenance": {
            "data_origin": "synthetic",
            "statement": (
                "All scenarios are synthetic fixtures generated from "
                "deterministic builders or seeded generators. This "
                "benchmark never processes real SOC/CSE/NCIIPC/"
                "CIC-IDS2017/BOTS data and must never be cited as "
                "evidence of real-world validation."),
        },
        "scenarios": scenarios,
        "permitted_side_effects": PERMITTED_SIDE_EFFECTS,
        "false_positive_policy": (
            "emitted signal families outside declared_expected_signals "
            "(plus any explicitly permitted side effect, of which there "
            "are none declared) are counted as false positives and also "
            "reported per-scenario as extra_families"),
        "seeds": {
            "scenario_fixtures": "deterministic — no randomness",
            "workload_population": workload_seed,
        },
        "generator_version": {
            "satsa": SATSA_VERSION,
            "scenario_builders": "satsa.analysis.compval.SCENARIO_MAP",
            "ground_truth_catalog": GROUND_TRUTH_SOURCE,
        },
        "metrics": {
            "scenario_family_precision_recall_f1": (
                "corpus micro-average over executable scenarios: "
                "tp=|expected∩emitted|, fn=|expected−emitted|, "
                "fp=|emitted−expected| per scenario"),
            "action_alignment": (
                "fraction of executed scenarios whose emitted supervisor "
                "decision equals the catalog's declared expected_action"),
            "coverage": (
                "executed vs not_executed scenario counts with reasons"),
            "prioritization": (
                "simulated recall@K and review-volume-to-find-all for "
                "SAT-SA entity prioritization vs a measured random-order "
                "baseline (labels = generator-config pathological/clean)"),
            "closure_time_baselines": (
                "z-score/MAD/IQR/fixed-threshold/random vs the real "
                "FastClosureWorker on closure times whose labels are "
                "stated by construction"),
            "ablation": (
                "finding families lost when exactly one default worker "
                "is removed, measured through the real RunService"),
        },
        "limitations": list(LIMITATIONS),
    }


def validate_manifest(manifest: dict) -> None:
    """Fail clearly (ValueError) if the manifest is malformed or its
    declared labels disagree with the authoritative catalog.

    Also enforces the ground-truth rule structurally: the declared
    expected signals must equal the catalog's expected signals, so a
    manifest that has been edited to flatter detector output cannot
    pass silently.
    """
    required_keys = (
        "benchmark_name", "benchmark_version", "ground_truth_source",
        "provenance", "scenarios", "seeds", "limitations")
    for key in required_keys:
        if key not in manifest:
            raise ValueError(f"manifest missing required key: {key!r}")
    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict) or \
            provenance.get("data_origin") != "synthetic":
        raise ValueError(
            "manifest.provenance.data_origin must be 'synthetic' — this "
            "benchmark measures controlled synthetic scenarios only")
    if not isinstance(manifest.get("scenarios"), list) or \
            not manifest["scenarios"]:
        raise ValueError("manifest.scenarios must be a non-empty list")
    if not manifest.get("limitations"):
        raise ValueError("manifest.limitations must be a non-empty list")

    from satsa.analysis.validate import synthetic_ground_truth
    catalog = {c.case_id: c for c in synthetic_ground_truth()}
    for entry in manifest["scenarios"]:
        case_id = entry.get("case_id")
        if case_id not in catalog:
            raise ValueError(
                f"manifest scenario {case_id!r} is not in the "
                "authoritative ground-truth catalog")
        declared = entry.get("declared_expected_signals")
        authoritative = sorted(catalog[case_id].expected_signals)
        if declared != authoritative:
            raise ValueError(
                f"manifest scenario {case_id!r} declares expected "
                f"signals {declared!r} but the authoritative catalog "
                f"(satsa.analysis.validate.synthetic_ground_truth) "
                f"declares {authoritative!r} — labels must come from "
                "the catalog, never from detector output or hand edits")


def read_pyproject_version() -> str:
    """Read the distribution version from pyproject.toml (best effort)."""
    try:
        with open(Path(__file__).resolve().parent.parent.parent /
                  "pyproject.toml", "rb") as fh:
            return tomllib.load(fh)["project"]["version"]
    except Exception:
        return "unknown"
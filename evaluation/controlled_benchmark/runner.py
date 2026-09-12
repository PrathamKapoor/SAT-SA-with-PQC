"""Controlled supervisory benchmark runner.

Executes the versioned controlled benchmark manifest against the REAL
SAT-SA pipeline — real ingestion (``SatsaService.submit``), real
analysis (``run_analysis``), real worker evaluation, real
prioritization — and scores the outputs against ground-truth labels
that were declared *before* any run
(``satsa.analysis.validate.synthetic_ground_truth`` and
generator-config population labels). No metric here is ever computed
by scoring a detector against its own output.

Three result classes are kept strictly separated:

* ``scenario_corpus`` — SAT-SA detector results vs the declared catalog;
* ``closure_time_baselines`` — statistical baselines vs the real
  FastClosureWorker, both scored against labels stated by construction;
* ``prioritization`` / ``ablation`` — the existing workload experiment
  and ablation runner, reused rather than reimplemented.

Same seed + same code + same inputs produce equivalent ``metrics``;
timestamps live in separate top-level fields and never enter metric
comparison. Results are returned as a dict; a JSON file is written
only when the caller passes an explicit ``output_dir`` (never into
tracked source directories by default).
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
import tempfile
import time
from pathlib import Path

from evaluation.controlled_benchmark.manifest import (
    BENCHMARK_NAME,
    BENCHMARK_VERSION,
    build_manifest,
    read_pyproject_version,
    validate_manifest,
)


# ---------------------------------------------------------------------------
# Metrics (pure functions over DECLARED labels + emitted outputs)
# ---------------------------------------------------------------------------

def _prf(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    if precision is None or recall is None or (precision + recall) == 0:
        f1 = None
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return {
        "tp": tp, "fp": fp, "fn": fn,
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "f1": round(f1, 4) if f1 is not None else None,
    }


def scenario_family_metrics(expected: list[str], emitted: list[str]) -> dict:
    """Confusion counts for one scenario at the declared signal-family
    level. ``expected`` comes from the ground-truth catalog; ``emitted``
    from the real pipeline run. Unknown never becomes zero or 100%: an
    undefined ratio is reported as None."""
    expected_set, emitted_set = set(expected), set(emitted)
    tp = len(expected_set & emitted_set)
    fn = len(expected_set - emitted_set)
    fp = len(emitted_set - expected_set)
    m = _prf(tp, fp, fn)
    m["expected_families"] = sorted(expected_set)
    m["emitted_families"] = sorted(emitted_set)
    m["extra_families"] = sorted(emitted_set - expected_set)
    m["missing_families"] = sorted(expected_set - emitted_set)
    return m


def corpus_micro_metrics(per_scenario: list[dict]) -> dict:
    """Micro-average the per-scenario family confusion counts."""
    tp = sum(s["metrics"]["tp"] for s in per_scenario)
    fp = sum(s["metrics"]["fp"] for s in per_scenario)
    fn = sum(s["metrics"]["fn"] for s in per_scenario)
    return _prf(tp, fp, fn)


# ---------------------------------------------------------------------------
# Scenario corpus execution through the REAL pipeline
# ---------------------------------------------------------------------------

def _hash_submission_dir(d: Path) -> dict:
    """sha256 per input CSV — the input-artifact hashes the manifest
    promises ('where applicable'). Deterministic content digests."""
    hashes = {}
    if d.exists():
        for f in sorted(d.iterdir()):
            if f.is_file():
                hashes[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
    return hashes


def _emitted_families_and_action(service, run_id: str) -> tuple[list[str], str]:
    """Collect the run's emitted signal families and the supervisor
    decision the recommendation engine would emit for the
    highest-confidence emitted family. Same documented rule as
    ``satsa.analysis.compval._emitted_families_and_action``, but with
    the confidence JSON parsed correctly (that module's helper never
    imports ``json``, so its 'best confidence' branch cannot fire; this
    runner must not silently inherit that behavior in a measurement)."""
    import json

    from satsa.analysis.recommend import recommend
    from satsa.supervisor.engine import (
        _SATSA_RECOMMENDATION_TO_DECISION,
    )

    rows = service._db.query_all(
        "SELECT f.rule_or_category, f.confidence_json FROM satsa_findings f"
        " JOIN satsa_observations o ON o.id = f.observation_id"
        " WHERE o.run_id = ? AND f.state = 'signal'", (run_id,))
    families = sorted({r.get("rule_or_category", "") for r in rows})
    if not families:
        return [], "SATSA_SURFACE"
    best_conf = -1.0
    best_family = families[0]
    for r in rows:
        try:
            conf_json = json.loads(r.get("confidence_json") or "{}")
        except (ValueError, TypeError):
            conf_json = {}
        score = float(conf_json.get("overall", 0.0))
        family = r.get("rule_or_category", "")
        if score > best_conf:
            best_conf = score
            best_family = family
    rec_action = _SATSA_RECOMMENDATION_TO_DECISION.get(
        recommend({
            "rule_or_category": best_family,
            "id": "cbench",
            "evidence_refs": [],
        }).action,
        "SATSA_SURFACE",
    )
    return families, rec_action


def _run_scenarios(engine, *, trust_key_dir) -> tuple[list[dict], list[dict]]:
    """Ingest + analyze every executable scenario fixture through the
    real pipeline and score it against the declared catalog labels."""
    from satsa.analysis.compval import NOT_EXECUTABLE_REASON, SCENARIO_MAP
    from satsa.analysis.synth import _write_cse
    from satsa.analysis.validate import synthetic_ground_truth
    from satsa.service import SatsaService

    service = SatsaService(engine)
    executed: list[dict] = []
    not_executed: list[dict] = []

    for case in synthetic_ground_truth():
        if case.case_id not in SCENARIO_MAP:
            not_executed.append({
                "case_id": case.case_id,
                "scenario": case.scenario,
                "reason": NOT_EXECUTABLE_REASON.get(
                    case.case_id,
                    "No deterministic single-entity fixture exists; the "
                    "runner refuses to fabricate one."),
            })
            continue

        builder = SCENARIO_MAP[case.case_id]
        cse, _omitted = builder()
        run = ingest = entity = assessment = None
        input_hashes: dict = {}
        with tempfile.TemporaryDirectory(prefix="cbench-scen-") as td:
            d = Path(td) / case.scenario
            _write_cse(cse, d)
            input_hashes = _hash_submission_dir(d)
            entity = service.register_entity(
                f"CBENCH-{case.case_id}", sector="defence",
                environment_class="on-prem")
            assessment = service.open_assessment(
                entity.id, 1735689600.0, 1735689600.0 + 86400 * 31)
            ingest = service.submit(assessment.id, d)
            if ingest.status != "accepted":
                not_executed.append({
                    "case_id": case.case_id,
                    "scenario": case.scenario,
                    "reason": f"Ingestion failed: status={ingest.status}",
                })
                continue
            run = service.run_analysis(
                entity.id, assessment.id, trust_key_dir=trust_key_dir)
            if run.status not in ("completed", "partial"):
                not_executed.append({
                    "case_id": case.case_id,
                    "scenario": case.scenario,
                    "reason": f"Analysis run failed: {run.status}",
                })
                continue
            emitted_families, emitted_action = _emitted_families_and_action(
                service, run.run_id)

        executed.append({
            "case_id": case.case_id,
            "scenario": case.scenario,
            "run_id": run.run_id,
            "entity_id": entity.id,
            "assessment_id": assessment.id,
            "input_artifact_sha256": input_hashes,
            "declared_labels": {
                "expected_signals": sorted(case.expected_signals),
                "expected_action": case.expected_action,
                "source": "satsa.analysis.validate.synthetic_ground_truth",
            },
            "metrics": scenario_family_metrics(
                case.expected_signals, emitted_families),
            "action": {
                "expected": case.expected_action,
                "emitted": emitted_action,
                "ok": emitted_action == case.expected_action,
            },
        })
    return executed, not_executed


# ---------------------------------------------------------------------------
# Closure-time baseline comparison (labels stated by construction)
# ---------------------------------------------------------------------------

def _closure_baseline_section(*, seed: int = 42) -> dict:
    """Deterministic closure-time corpus: fast closures are positive by
    construction, normal-paced closures negative by construction — the
    same discipline as tests/test_phase77 (never derived from detector
    output). The real FastClosureWorker runs over a real
    CanonicalDataset; compare_closure_time_detectors scores every
    statistical baseline plus SAT-SA against the SAME labels."""
    from evaluation.baselines.compare import compare_closure_time_detectors
    from satsa.analysis.workers.fast_closure import FastClosureWorker
    from satsa.contracts.worker import RunContext, SnapshotRef
    from satsa.domain.workflow import Alert
    from satsa.store.dataset import CanonicalDataset

    base = 1735689600.0
    # Deliberate construction: 9 normal-paced critical closures
    # (700-950s, above the documented 600s critical fast-closure SLA)
    # and 3 deliberately fast closures (40-90s). Labels precede any run.
    close_times = [700, 800, 900, 750, 850, 950, 720, 780, 880,
                   40, 60, 90]
    labels = [False] * 9 + [True] * 3
    severities = ["critical"] * len(close_times)

    alerts = []
    for i, (ct, sev) in enumerate(zip(close_times, severities)):
        alerts.append(Alert(
            entity_id="cbench-e", assessment_id="cbench-a",
            native_id=f"CB-ALERT-{i:03d}",
            created_at=base, mapped_severity=sev,
            acknowledged_at=base + 10, closed_at=base + 10 + ct,
            source_record_ref=f"cbench-sr-{i}"))
    dataset = CanonicalDataset(
        entity_id="cbench-e", assessment_id="cbench-a",
        snapshot_digest="cbench-d", alerts=alerts, cases=[], steps=[],
        escalations=[], dispositions=[], assets=[],
        submitted_categories=frozenset(
            ("alerts", "cases", "investigation_steps", "escalations",
             "dispositions", "assets")))
    worker = FastClosureWorker()
    batch = worker.evaluate(
        SnapshotRef("cbench-d", "cbench-e", "cbench-a"), dataset, [], None,
        RunContext(run_id="cbench-r", entity_id="cbench-e",
                   assessment_id="cbench-a"))
    flagged = {aid for f in batch.findings for aid in f.scoped_subjects}
    # scoped_subjects carry the Alert domain id (a per-construction
    # random id, exactly as tests/test_phase77 does) — native_id would
    # never match and would silently score the real worker as 0.
    satsa_flags = [a.id in flagged for a in dataset.alerts]

    comparison = compare_closure_time_detectors(
        close_times, labels, satsa_flags=satsa_flags, seed=seed)
    return {
        "label_origin": "construction — fast closures were built fast, "
                        "normal closures slow, before any detector ran",
        "n_records": len(close_times),
        "n_positive_labels": sum(labels),
        "comparison": comparison,
    }


# ---------------------------------------------------------------------------
# Full benchmark
# ---------------------------------------------------------------------------

def run_benchmark(*, trust_key_dir=None, workload_seed: int = 42,
                  n_population: int = 10, n_pathological: int = 4,
                  n_random_trials: int = 200,
                  include_ablation: bool = True) -> dict:
    """Execute the controlled benchmark end to end.

    All heavy state (scratch DB, generated submissions, workload
    generation dirs, PQC keys) lives beside ``trust_key_dir``: when the
    caller supplies it, the caller owns the location (it should point
    outside any tracked tree); otherwise the runner creates a temp dir
    and removes it afterwards.
    """
    from evaluation.ablation.runner import run_ablation_study
    from evaluation.workload import build_population, run_workload_experiment
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    from satsa import __version__ as satsa_version

    manifest = build_manifest(workload_seed=workload_seed)
    validate_manifest(manifest)

    started = time.time()
    own_temp = None
    engine = None
    if trust_key_dir is None:
        own_temp = tempfile.mkdtemp(prefix="cbench-")
        trust_key_dir = Path(own_temp) / "keys"
        trust_key_dir.mkdir(parents=True, exist_ok=True)
    trust_key_dir = Path(trust_key_dir)

    try:
        # The scratch DB lives INSIDE the owned keys directory so two
        # runs with sibling key dirs can never share analytical state
        # (a shared DB would leak peer/cross-entity signals between
        # runs and destroy determinism).
        engine = SQLiteDatabaseEngine(trust_key_dir / "cbench.db")
        engine.connect()
        MigrationRunner(engine).migrate()

        scenario_executed, scenario_not_executed = _run_scenarios(
            engine, trust_key_dir=trust_key_dir)

        per_scenario = [
            {
                "case_id": s["case_id"],
                "scenario": s["scenario"],
                "metrics": s["metrics"],
                "action": s["action"],
                "declared_labels": s["declared_labels"],
            }
            for s in scenario_executed
        ]
        action_total = len(per_scenario)
        action_ok = sum(1 for s in per_scenario if s["action"]["ok"])

        metrics = {
            "scenario_corpus": {
                "coverage": {
                    "catalog_size": len(manifest["scenarios"]),
                    "executed": len(scenario_executed),
                    "not_executed": len(scenario_not_executed),
                    "not_executed_reasons": scenario_not_executed,
                },
                "micro": corpus_micro_metrics(per_scenario),
                "action_alignment": {
                    "ok": action_ok,
                    "total": action_total,
                    "rate": round(action_ok / action_total, 4)
                    if action_total else None,
                },
                "per_scenario": per_scenario,
            },
            "closure_time_baselines": _closure_baseline_section(),
        }

        # Prioritization — the existing workload experiment (labels from
        # generator configuration, never from detector output).
        population = build_population(
            engine, n_entities=n_population,
            n_pathological=n_pathological, seed=workload_seed,
            trust_key_dir=trust_key_dir)
        workload = run_workload_experiment(
            engine, population, n_random_trials=n_random_trials,
            rng_seed=workload_seed + 1)
        metrics["prioritization"] = workload.to_dict()

        # Ablation — existing runner over the 'mixed' scenario scope
        # (the scope expected to emit multiple families, so ablation has
        # something real to remove).
        if include_ablation:
            mixed = next((s for s in scenario_executed
                          if s["case_id"] == "mixed"), None)
            if mixed is None:
                metrics["ablation"] = {
                    "status": "not_applicable",
                    "reason": "the 'mixed' scenario scope did not execute, "
                              "so no ablation scope exists",
                }
            else:
                metrics["ablation"] = run_ablation_study(
                    engine, mixed["entity_id"], mixed["assessment_id"])

        finished = time.time()
        return {
            "benchmark_name": BENCHMARK_NAME,
            "benchmark_version": BENCHMARK_VERSION,
            "environment": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "satsa_version": satsa_version,
                "package_version": read_pyproject_version(),
            },
            "started_at": started,
            "finished_at": finished,
            "metrics": metrics,
            "provenance_note": manifest["provenance"]["statement"],
            "limitations": list(manifest["limitations"]),
        }
    finally:
        import shutil
        if engine is not None:
            try:
                engine.close()
            except Exception:
                pass
        if own_temp:
            shutil.rmtree(own_temp, ignore_errors=True)


def write_results(results: dict, output_dir: Path) -> Path:
    """Write machine-readable results to an explicitly chosen output
    directory (created if needed). Never called implicitly."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / "controlled-benchmark-results.json"
    out.write_text(
        json.dumps(results, indent=2, default=str), encoding="utf-8")
    return out
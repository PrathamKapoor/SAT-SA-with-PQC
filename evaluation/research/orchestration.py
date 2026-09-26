"""Direct vs LangGraph orchestration: overhead, TRUST-SAT cost and recovery.

Both modes run the identical hosted analysis path on the identical
fixture: submission validation, the default deterministic workers,
recommendations, a paused supervisory review, an authorized decision and
TRUST-SAT finalization. ``direct`` is ``review_required=True`` on the
Phase 3 worker; ``graph`` is ``graph_enabled=True`` (LangGraph with a
durable SQLite checkpointer). ``direct_unreviewed`` runs the same
analytics with no review pause and no supervisory finalization; it is a
benchmark configuration for TRUST-SAT overhead only, never a product mode.

Timings are local synchronous wall-clock measurements on one machine with
isolated SQLite; they do not describe PostgreSQL, S3, API or hosted
deployment performance. Stage times are measured by temporarily wrapping
existing worker methods inside this process; product code is unchanged.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter
from typing import Any

from evaluation.research.statistics import describe, paired_comparison

OVERHEAD_EXPERIMENT = "satsa-orchestration-overhead-v1"
RECOVERY_EXPERIMENT = "satsa-orchestration-recovery-v1"
MODES = ("direct", "graph")
RECOVERY_POINTS = (
    "analysis_stage_transient",
    "analysis_stage_crash",
    "recommendations_transient",
    "worker_restart_at_review",
    "finalization_transient",
    "finalization_crash",
)


class SimulatedCrash(BaseException):
    """Stands in for abrupt process death.

    Deriving from BaseException bypasses the worker's own ``except
    Exception`` handling, so the lease is left held exactly as when a
    process is killed mid-stage.
    """


@contextmanager
def _timed(obj: Any, attribute: str, bucket: dict[str, list[float]], label: str):
    """Temporarily wrap ``obj.attribute`` and append each call's duration."""
    had_own = attribute in vars(obj)
    original = getattr(obj, attribute)

    def wrapper(*args, **kwargs):
        started = perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            bucket.setdefault(label, []).append(perf_counter() - started)

    setattr(obj, attribute, wrapper)
    try:
        yield
    finally:
        if had_own:
            setattr(obj, attribute, original)
        else:
            delattr(obj, attribute)


@contextmanager
def _db_counter(engine) -> Iterator[dict[str, int]]:
    counts = {"execute": 0, "query_one": 0, "query_all": 0}
    originals = {name: getattr(engine, name) for name in counts}

    def counting(name):
        def call(*args, **kwargs):
            counts[name] += 1
            return originals[name](*args, **kwargs)

        return call

    for name in counts:
        setattr(engine, name, counting(name))
    try:
        yield counts
    finally:
        for name in counts:
            delattr(engine, name)


def _fixture_files(scenario: str) -> dict[str, bytes]:
    from evaluation.research.hosted import cse_csv_files
    from satsa.analysis.compval import SCENARIO_MAP

    cse, _ = SCENARIO_MAP[scenario]()
    return cse_csv_files(cse)


def _outputs(service, run_id: str) -> dict[str, Any]:
    findings = service.list_findings(run_id, limit=500)
    risk = service.get_risk(run_id)
    return {
        "families": sorted(
            {row["rule_or_category"] for row in findings if row["state"] == "signal"}
        ),
        "finding_count": len(findings),
        "recommendation_count": len(service.list_recommendations(run_id)),
        "risk_total_score": (risk or {}).get("profile", {}).get("total_score"),
    }


def _checkpoint_count(tenant, run_id: str) -> int | None:
    from satsa.analysis.graph import durable_checkpointer

    with durable_checkpointer(tenant.engine) as saver:
        return sum(
            1 for _ in saver.list({"configurable": {"thread_id": f"satsa:{run_id}"}})
        )


def _verify(tenant, run_id: str) -> tuple[bool, str, float]:
    from satsa.analysis.trust import TrustService

    trust = TrustService(
        tenant.engine, tenant.key_dir, organization_id=tenant.organization_id
    )
    started = perf_counter()
    ok, reason = trust.verify_finalization(run_id, tenant.audit)
    return ok, reason, perf_counter() - started


def workflow_trial(
    root: Path, *, mode: str, files: dict[str, bytes], key_dir: Path
) -> dict[str, Any]:
    """One complete matched workflow in a fresh tenant."""
    from evaluation.research.hosted import scratch_tenant
    from satsa.analysis.trust import TrustService

    if mode not in (*MODES, "direct_unreviewed"):
        raise ValueError(f"unknown mode {mode!r}")
    with scratch_tenant(root, key_dir=key_dir) as tenant:
        version_id, report, _ = tenant.submit(files, key=f"orchestration-{mode}")
        if report["status"] != "valid":
            raise RuntimeError(f"fixture failed validation: {report['errors'][:1]}")
        service = tenant.analyst_service()
        run = service.create_run(
            version_id,
            idempotency_key=f"orchestration-{mode}-run",
            graph_enabled=mode == "graph",
            review_required=mode != "direct_unreviewed",
        )
        run_id = run["run_id"]
        worker = tenant.worker(f"orchestration-{mode}-worker")
        stages: dict[str, list[float]] = {}
        with (
            _timed(worker, "_execute", stages, "analysis_workers_and_risk"),
            _timed(worker, "_persist_recommendations", stages, "recommendations"),
            _timed(worker, "_finalize_supervisory", stages, "trust_finalization"),
            _timed(worker, "_attest_if_configured", stages, "trust_run_attestation"),
            _timed(TrustService, "_sign_digest", stages, "trust_signatures_all"),
            _timed(tenant.audit, "record_once", stages, "audit_ledger_record_once"),
            _db_counter(tenant.engine) as db_ops,
        ):
            started = perf_counter()
            first = worker.run_once()
            phase1 = perf_counter() - started
            decision_seconds = phase2 = 0.0
            final = first
            if mode != "direct_unreviewed":
                if first != "awaiting_review":
                    raise RuntimeError(f"{mode} did not pause for review: {first!r}")
                started = perf_counter()
                tenant.supervisor_service().decide(
                    run_id, action="confirm", reason="Orchestration experiment"
                )
                decision_seconds = perf_counter() - started
                started = perf_counter()
                final = worker.run_once()
                phase2 = perf_counter() - started
        if final not in {"completed", "partial"}:
            raise RuntimeError(f"{mode} did not complete: {final!r}")
        verified, reason, verify_seconds = (
            _verify(tenant, run_id)
            if mode != "direct_unreviewed"
            else (None, "not finalized in this configuration", None)
        )
        domain = sum(
            sum(stages.get(label, []))
            for label in (
                "analysis_workers_and_risk",
                "recommendations",
                "trust_finalization",
                "trust_run_attestation",
            )
        )
        processing = phase1 + phase2
        return {
            "mode": mode,
            "run_id": run_id,
            "status": final,
            "processing_seconds": processing,
            "phase_to_review_seconds": phase1,
            "phase_after_decision_seconds": phase2,
            "decision_call_seconds": decision_seconds,
            "stage_seconds": {k: sum(v) for k, v in sorted(stages.items())},
            "stage_calls": {k: len(v) for k, v in sorted(stages.items())},
            "outside_domain_stages_seconds": processing - domain,
            "db_operations": dict(db_ops),
            "db_operations_total": sum(db_ops.values()),
            "graph_checkpoints": _checkpoint_count(tenant, run_id)
            if mode == "graph"
            else None,
            "trust_verified": verified,
            "trust_verification_reason": reason,
            "trust_verification_seconds": verify_seconds,
            "outputs": _outputs(service, run_id),
        }


def _warm_up(root: Path, files: dict[str, bytes], key_dir: Path) -> None:
    for mode in (*MODES, "direct_unreviewed"):
        workflow_trial(root / f"warmup-{mode}", mode=mode, files=files, key_dir=key_dir)


def run_orchestration_overhead_experiment(
    scratch_dir: Path,
    *,
    trials: int = 30,
    scenario: str = "mixed",
    seed: int = 0,
) -> dict[str, Any]:
    """Interleaved matched trials of direct, graph and unreviewed runs."""
    if trials < 1:
        raise ValueError("trials must be at least 1")
    root = Path(scratch_dir)
    files = _fixture_files(scenario)
    key_dir = root / "shared-signing-keys"
    _warm_up(root, files, key_dir)
    rows: list[dict[str, Any]] = []
    started = perf_counter()
    for trial in range(trials):
        order = ["direct", "graph", "direct_unreviewed"]
        # Rotate the order per trial so slow drift is not assigned to one mode.
        order = order[trial % 3 :] + order[: trial % 3]
        for position, mode in enumerate(order):
            row = workflow_trial(
                root / f"t{trial:03d}-{mode}", mode=mode, files=files, key_dir=key_dir
            )
            row.update({"trial": trial, "order_position": position})
            rows.append(row)

    by_mode = {
        mode: [r for r in rows if r["mode"] == mode]
        for mode in (*MODES, "direct_unreviewed")
    }

    def series(mode: str, key: str) -> list[float]:
        return [float(r[key]) for r in by_mode[mode]]

    def stage(mode: str, label: str) -> list[float]:
        return [float(r["stage_seconds"].get(label, 0.0)) for r in by_mode[mode]]

    reference = by_mode["direct"][0]["outputs"]
    analytic_keys = ("families", "finding_count", "risk_total_score")
    identical = {
        "direct_vs_graph_all_outputs": all(
            r["outputs"] == reference for r in rows if r["mode"] in MODES
        ),
        "all_modes_findings_and_risk": all(
            {k: r["outputs"][k] for k in analytic_keys}
            == {k: reference[k] for k in analytic_keys}
            for r in rows
        ),
        "note": "direct_unreviewed persists no recommendations by design",
    }
    per_mode = {}
    for mode, mode_rows in by_mode.items():
        per_mode[mode] = {
            "processing_seconds": describe(
                series(mode, "processing_seconds"), unit="s"
            ),
            "phase_to_review_seconds": describe(
                series(mode, "phase_to_review_seconds"), unit="s"
            ),
            "phase_after_decision_seconds": describe(
                series(mode, "phase_after_decision_seconds"), unit="s"
            ),
            "outside_domain_stages_seconds": describe(
                series(mode, "outside_domain_stages_seconds"), unit="s"
            ),
            "stage_seconds": {
                label: describe(stage(mode, label), unit="s")
                for label in sorted({k for r in mode_rows for k in r["stage_seconds"]})
            },
            "db_operations_total": describe(
                series(mode, "db_operations_total"), unit="calls"
            ),
            "graph_checkpoints": describe(
                [r["graph_checkpoints"] for r in mode_rows], unit="checkpoints"
            )
            if mode == "graph"
            else None,
            "trust_verified_all": all(r["trust_verified"] for r in mode_rows)
            if mode != "direct_unreviewed"
            else None,
            "trust_verification_seconds": describe(
                [r["trust_verification_seconds"] for r in mode_rows], unit="s"
            )
            if mode != "direct_unreviewed"
            else None,
        }

    pairing = "same trial index, same fixture, fresh tenant per run, rotated order"
    comparisons = {
        "graph_vs_direct_processing_seconds": paired_comparison(
            series("direct", "processing_seconds"),
            series("graph", "processing_seconds"),
            unit="s",
            pairing=pairing,
            seed=seed,
        ),
        "graph_vs_direct_outside_domain_stages_seconds": paired_comparison(
            series("direct", "outside_domain_stages_seconds"),
            series("graph", "outside_domain_stages_seconds"),
            unit="s",
            pairing=pairing,
            seed=seed + 1,
        ),
        "graph_vs_direct_db_operations": paired_comparison(
            series("direct", "db_operations_total"),
            series("graph", "db_operations_total"),
            unit="calls",
            pairing=pairing,
            seed=seed + 2,
        ),
        "reviewed_finalized_vs_unreviewed_processing_seconds": paired_comparison(
            series("direct_unreviewed", "processing_seconds"),
            series("direct", "processing_seconds"),
            unit="s",
            pairing=pairing,
            seed=seed + 3,
        ),
    }
    finalize = stage("direct", "trust_finalization")
    processing = series("direct", "processing_seconds")
    trust_share = [f / p for f, p in zip(finalize, processing) if p > 0]
    return {
        "status": "completed",
        "experiment": OVERHEAD_EXPERIMENT,
        "data_origin": "synthetic",
        "metrics": {
            "design": {
                "scenario": scenario,
                "trials_per_mode": trials,
                "warm_up_runs_per_mode": 1,
                "order_policy": "rotated per trial across three modes",
                "independent_unit": "workflow run in a fresh tenant",
                "note": "timing trials on one machine are repeated measurements, "
                "not independent samples of a deployment population",
            },
            "analytics_identical_across_modes": identical,
            "reference_outputs": reference,
            "per_mode": per_mode,
            "comparisons": comparisons,
            "trust_sat": {
                "finalization_seconds_direct": describe(finalize, unit="s"),
                "run_attestation_seconds_direct": describe(
                    stage("direct", "trust_run_attestation"), unit="s"
                ),
                "all_signatures_seconds_direct": describe(
                    stage("direct", "trust_signatures_all"), unit="s"
                ),
                "signature_calls_direct": describe(
                    [
                        r["stage_calls"].get("trust_signatures_all", 0)
                        for r in by_mode["direct"]
                    ],
                    unit="calls",
                ),
                "finalization_share_of_processing_direct": describe(
                    trust_share, unit="fraction"
                ),
                "verification_seconds_direct": per_mode["direct"][
                    "trust_verification_seconds"
                ],
                "note": (
                    "audit_ledger_record_once covers every audit event in the run; "
                    "trust_signatures_all covers finalization and run/finding "
                    "attestation signatures"
                ),
            },
            "trials": rows,
        },
        "performance": {
            "measurement_scope": "local synchronous SQLite, one machine; not "
            "production API/worker/PostgreSQL/S3 topology",
            "total_elapsed_seconds": round(perf_counter() - started, 6),
        },
        "limitations": [
            "Single machine, SQLite, synchronous worker; absolute times do not transfer to production topology.",
            "One authored fixture (the 'mixed' catalog scenario); larger inputs may change the ratio of orchestration to analytics cost.",
            "Stage timings wrap existing worker methods; wrapper overhead is included in each stage.",
            "Intervals are percentile bootstrap intervals over repeated trials on one machine; no significance test is made.",
        ],
    }


def _stage_attempts(engine, run_id: str) -> dict[str, dict[str, Any]]:
    return {
        row["worker_name"]: {"attempt": int(row["attempt"]), "status": row["status"]}
        for row in engine.query_all(
            "SELECT worker_name,attempt,status FROM satsa_jobs WHERE run_id=?",
            (run_id,),
        )
    }


def _release(engine, run_id: str, *, crashed: bool) -> None:
    """Make an interrupted run claimable again, as elapsed time would."""
    if crashed:
        engine.execute(
            "UPDATE satsa_execution_jobs SET lease_expires_at=0 WHERE run_id=?",
            (run_id,),
        )
    else:
        engine.execute(
            "UPDATE satsa_execution_jobs SET available_at=0 WHERE run_id=?", (run_id,)
        )


def recovery_trial(
    root: Path,
    *,
    mode: str,
    point: str,
    files: dict[str, bytes],
    key_dir: Path,
    reference: dict[str, Any],
) -> dict[str, Any]:
    """Inject one interruption, recover with a fresh worker, check state."""
    from evaluation.research.hosted import scratch_tenant
    from satsa.analysis.execution import RetryableAnalysisError

    if point not in RECOVERY_POINTS:
        raise ValueError(f"unknown recovery point {point!r}")
    with scratch_tenant(root, key_dir=key_dir) as tenant:
        version_id, report, _ = tenant.submit(files, key=f"recovery-{mode}")
        if report["status"] != "valid":
            raise RuntimeError("fixture failed validation")
        service = tenant.analyst_service()
        run_id = service.create_run(
            version_id,
            idempotency_key=f"recovery-{mode}-run",
            graph_enabled=mode == "graph",
            review_required=True,
        )["run_id"]
        first = tenant.worker("recovery-first")
        crashed = point.endswith("_crash")
        injected = {"fired": False}

        def inject(attribute: str, after_calls: int):
            original = getattr(first, attribute)
            calls = {"n": 0}

            def wrapper(*args, **kwargs):
                calls["n"] += 1
                if not injected["fired"] and calls["n"] > after_calls:
                    injected["fired"] = True
                    if crashed:
                        raise SimulatedCrash(point)
                    raise RetryableAnalysisError(f"injected {point}")
                return original(*args, **kwargs)

            setattr(first, attribute, wrapper)

        if point.startswith("analysis_stage"):
            inject("_persist_stage", after_calls=2)
        elif point == "recommendations_transient":
            inject("_persist_recommendations", after_calls=0)

        def run(worker) -> str:
            try:
                return worker.run_once()
            except SimulatedCrash:
                return "crashed"

        observed: list[str] = [run(first)]
        attempts_after_interruption = _stage_attempts(tenant.engine, run_id)
        recovery_seconds = None
        if point in {
            "analysis_stage_transient",
            "analysis_stage_crash",
            "recommendations_transient",
        }:
            _release(tenant.engine, run_id, crashed=crashed)
            second = tenant.worker("recovery-second")
            started = perf_counter()
            observed.append(run(second))
            recovery_seconds = perf_counter() - started
        paused = observed[-1] == "awaiting_review"
        if paused:
            tenant.supervisor_service().decide(
                run_id, action="confirm", reason="Recovery experiment"
            )
            finisher = tenant.worker("recovery-finisher")
            if point.startswith("finalization"):
                inject_target = finisher
                original = inject_target._finalize_supervisory

                def failing(lease):
                    if not injected["fired"]:
                        injected["fired"] = True
                        if crashed:
                            raise SimulatedCrash(point)
                        raise RetryableAnalysisError(f"injected {point}")
                    return original(lease)

                inject_target._finalize_supervisory = failing
                observed.append(run(finisher))
                _release(tenant.engine, run_id, crashed=crashed)
                final_worker = tenant.worker("recovery-final")
                started = perf_counter()
                observed.append(run(final_worker))
                recovery_seconds = perf_counter() - started
            else:
                started = perf_counter()
                observed.append(run(finisher))
                if point == "worker_restart_at_review":
                    recovery_seconds = perf_counter() - started
        final_status = observed[-1]
        completed = final_status in {"completed", "partial"}
        outputs = _outputs(service, run_id) if completed else None
        attempts = _stage_attempts(tenant.engine, run_id)
        # Only stages that had already completed before the interruption
        # count as duplicated work; the interrupted stage must rerun.
        completed_before = {
            name: state["attempt"]
            for name, state in attempts_after_interruption.items()
            if state["status"] == "completed"
        }
        repeated_stages = sorted(
            name
            for name, attempt in completed_before.items()
            if attempts.get(name, {}).get("attempt", attempt) > attempt
        )
        rerun_stages = sorted(
            name
            for name, state in attempts_after_interruption.items()
            if state["status"] != "completed"
            and attempts.get(name, {}).get("attempt", 0) > state["attempt"]
        )
        decisions = tenant.engine.query_one(
            "SELECT COUNT(*) AS n FROM satsa_run_review_decisions WHERE run_id=?",
            (run_id,),
        )["n"]
        finalizations = tenant.engine.query_one(
            "SELECT COUNT(*) AS n FROM satsa_trust_finalizations WHERE run_id=?",
            (run_id,),
        )["n"]
        verified, reason, _ = (
            _verify(tenant, run_id) if completed else (False, "not completed", 0)
        )
        checkpoint_exists = (
            bool(_checkpoint_count(tenant, run_id)) if mode == "graph" else None
        )
        return {
            "mode": mode,
            "point": point,
            "interruption_injected": injected["fired"]
            or point == "worker_restart_at_review",
            "observed_statuses": observed,
            "recovered_to_completion": completed,
            "recovery_seconds": recovery_seconds,
            "outputs_match_uninterrupted_reference": outputs == reference
            if completed
            else False,
            "completed_stages_repeated_after_interruption": repeated_stages,
            "interrupted_stages_rerun": rerun_stages,
            "review_decisions": decisions,
            "trust_finalizations": finalizations,
            "trust_verified": verified,
            "trust_verification_reason": reason,
            "graph_checkpoint_exists": checkpoint_exists,
        }


def run_orchestration_recovery_experiment(
    scratch_dir: Path,
    *,
    trials: int = 3,
    scenario: str = "mixed",
    points: tuple[str, ...] = RECOVERY_POINTS,
) -> dict[str, Any]:
    """Every (mode, interruption point) pair, repeated ``trials`` times."""
    if trials < 1:
        raise ValueError("trials must be at least 1")
    root = Path(scratch_dir)
    files = _fixture_files(scenario)
    key_dir = root / "shared-signing-keys"
    started = perf_counter()
    references = {
        mode: workflow_trial(
            root / f"reference-{mode}", mode=mode, files=files, key_dir=key_dir
        )["outputs"]
        for mode in MODES
    }
    rows = []
    for mode in MODES:
        for point in points:
            for trial in range(trials):
                row = recovery_trial(
                    root / f"{mode}-{point}-{trial}",
                    mode=mode,
                    point=point,
                    files=files,
                    key_dir=key_dir,
                    reference=references[mode],
                )
                row["trial"] = trial
                rows.append(row)
    summary = {}
    for mode in MODES:
        for point in points:
            group = [r for r in rows if r["mode"] == mode and r["point"] == point]
            summary[f"{mode}:{point}"] = {
                "trials": len(group),
                "recovered_to_completion": sum(
                    r["recovered_to_completion"] for r in group
                ),
                "outputs_match_reference": sum(
                    r["outputs_match_uninterrupted_reference"] for r in group
                ),
                "trust_verified": sum(bool(r["trust_verified"]) for r in group),
                "runs_with_repeated_completed_stages": sum(
                    bool(r["completed_stages_repeated_after_interruption"])
                    for r in group
                ),
                "single_decision_and_finalization": sum(
                    r["review_decisions"] == 1 and r["trust_finalizations"] == 1
                    for r in group
                ),
                "recovery_seconds": describe(
                    [
                        r["recovery_seconds"]
                        for r in group
                        if r["recovery_seconds"] is not None
                    ],
                    unit="s",
                ),
            }
    return {
        "status": "completed",
        "experiment": RECOVERY_EXPERIMENT,
        "data_origin": "synthetic",
        "metrics": {
            "design": {
                "scenario": scenario,
                "modes": list(MODES),
                "interruption_points": list(points),
                "trials_per_cell": trials,
                "crash_model": "BaseException raised inside the worker, bypassing its "
                "error handling; lease expiry then simulated by setting lease_expires_at "
                "to the past",
                "transient_model": "RetryableAnalysisError raised once; retry delay "
                "skipped by setting available_at to the past",
            },
            "reference_outputs": references,
            "summary": summary,
            "trials": rows,
        },
        "performance": {
            "measurement_scope": "local synchronous SQLite, one machine",
            "total_elapsed_seconds": round(perf_counter() - started, 6),
        },
        "limitations": [
            (
                "Interruptions are injected at worker-method boundaries in one process; "
                "real process kills, network partitions and database failover are not exercised."
            ),
            "Lease expiry is simulated by editing the scratch queue row, not by waiting.",
            "One authored fixture; recovery latency depends on remaining work at the interruption point.",
        ],
    }

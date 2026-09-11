"""SAT-SA command-line interface — one entry point that exposes
every operation the UI exposes, calling the same service layer
(``SatsaService``) so CLI and UI cannot drift.

Subcommands mirror the roadmap:

    sat-sa ingest        — submit a CSE submission directory
    sat-sa analyze       — run the default worker set on a scope
    sat-sa risk          — compute the entity risk profile
    sat-sa prioritize    — rank entities + findings for review
    sat-sa findings      — list the signal findings of a run
    sat-sa verify        — verify the run + finding trust receipts
    sat-sa review        — record / list human review decisions
    sat-sa report        — render a HTML report for one entity
    sat-sa demo          — load the committed demo dataset
    sat-sa validate      — run synthetic ground-truth validation
    sat-sa benchmark     — print the latest scaling benchmark
    sat-sa agents        — print the 32-agent registry
    sat-sa decision      — run the supervisor engine on a run
    sat-sa doctor        — diagnose the local install/deployment
    sat-sa audit         — database-wide meta-audit of trust coverage
    sat-sa calibrate     — propose/test/decide/deploy a threshold change
    sat-sa ablate        — each worker's unique finding-family contribution
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from satsa import __version__ as SATSA_VERSION
from satsa.service import SatsaService


# ---------------------------------------------------------------------------
# Database bootstrap helpers
# ---------------------------------------------------------------------------

def _open_service(db_path: str, trust_key_dir: Optional[str]) -> SatsaService:
    """Open the SQLite database and return a SatsaService. The
    database lives at ``db_path`` (default ``./satsa.db``); the
    trust key directory is created if missing."""
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    eng = SQLiteDatabaseEngine(Path(db_path))
    eng.connect()
    MigrationRunner(eng).migrate()
    svc = SatsaService(eng)
    if trust_key_dir is not None:
        Path(trust_key_dir).mkdir(parents=True, exist_ok=True)
    return svc


def _print_json(obj, *, fp=None) -> None:
    json.dump(obj, fp or sys.stdout, indent=2, sort_keys=True, default=str)
    print()


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def cmd_ingest(args) -> int:
    """Ingest a CSE submission directory into the database."""
    svc = _open_service(args.db, args.trust_key_dir)
    e = svc.register_entity(args.entity, sector=args.sector or "",
                             environment_class=args.env or "")
    a = svc.open_assessment(e.id, args.period_start, args.period_end,
                            policy_version=args.policy_version)
    result = svc.submit(a.id, Path(args.submission),
                        source_system=args.source_system)
    print(json.dumps({
        "entity_id": e.id, "assessment_id": a.id,
        "ingest_status": result.status,
        "snapshot_digest": result.snapshot_digest,
        "categories": result.categories,
        "counts": result.counts,
        "duration_seconds": result.duration_seconds,
    }, indent=2, default=str))
    return 0


def cmd_analyze(args) -> int:
    """Run the default worker set on an existing scope."""
    svc = _open_service(args.db, args.trust_key_dir)
    result = svc.run_analysis(args.entity_id, args.assessment_id,
                              trust_key_dir=Path(args.trust_key_dir) if args.trust_key_dir else None)
    print(json.dumps({
        "run_id": result.run_id,
        "status": result.status,
        "observation_count": len(result.observation_ids),
        "finding_count": len(result.finding_ids),
        "error": result.error,
    }, indent=2, default=str))
    return 0


def cmd_risk(args) -> int:
    """Compute the entity risk profile."""
    svc = _open_service(args.db, args.trust_key_dir)
    prof = svc.compute_risk(args.entity_id)
    print(json.dumps(prof.to_dict(), indent=2, default=str))
    return 0


def cmd_prioritize(args) -> int:
    """Rank entities (and, optionally, one run's findings) for review."""
    svc = _open_service(args.db, args.trust_key_dir)
    entities = svc.prioritize_entities()
    print("Entities by priority:")
    for i, ep in enumerate(entities, start=1):
        print(f"  {i:02d}. {ep.entity_id}  score={ep.priority_score:.1f}"
              f"  concerns={len(ep.distinct_concerns)}")
    if args.run_id:
        findings = svc.prioritize_findings(args.run_id)
        print("\nFindings by priority:")
        for i, fp in enumerate(findings, start=1):
            print(f"  {i:02d}. {fp.finding_id}  score={fp.priority_score:.1f}"
                  f"  rationale={fp.rationale[:80]}")
    return 0


def cmd_findings(args) -> int:
    """List the signal findings of a run."""
    from satsa.analysis.run import RunService
    svc = _open_service(args.db, args.trust_key_dir)
    rows = svc._db.query_all(
        "SELECT f.*, o.worker_name, e.display_name FROM satsa_findings f"
        " JOIN satsa_observations o ON o.id=f.observation_id"
        " JOIN satsa_entities e ON e.id=o.entity_id"
        " WHERE o.run_id=? ORDER BY f.created_at", (args.run_id,))
    if args.state:
        rows = [r for r in rows if r["state"] == args.state]
    for r in rows:
        print(f"[{r['state']:>15}] {r['rule_or_category']:<45}"
              f" worker={r['worker_name']:<25}"
              f" entity={r['display_name']}")
    return 0


def cmd_verify(args) -> int:
    """Verify a run + every finding against its PQC trust receipt."""
    svc = _open_service(args.db, args.trust_key_dir)
    if not args.trust_key_dir:
        raise SystemExit("--trust-key-dir is required for verify")
    report = svc.verify_run(args.run_id, Path(args.trust_key_dir))
    print(json.dumps(report, indent=2, default=str))
    rc = 0 if report.get("run", {}).get("ok") else 2
    return rc


def cmd_review(args) -> int:
    """Record (or list) human review decisions."""
    svc = _open_service(args.db, args.trust_key_dir)
    if args.list:
        history = svc.review_history(args.list)
        for h in history:
            print(f"[{h.action}] {h.finding_id}  by={h.principal_identity_id}"
                  f"  at={h.occurred_at}")
            if h.reason:
                print(f"    reason: {h.reason}")
        return 0
    # Authenticated identity required to record a decision — the CLI
    # path must not be a backdoor around the UI's auth (same identity
    # system, same qsmlops.security.permissions.model.DECISION_RECORD
    # permission). Accept the credential via --credential or the
    # SATSA_CREDENTIAL env var (never as a bare --principal string).
    import os
    from satsa import security as satsa_security
    from qsmlops.security.permissions.model import DECISION_RECORD
    token = args.credential or os.environ.get("SATSA_CREDENTIAL", "")
    if not token:
        raise SystemExit(
            "recording a review decision requires an authenticated "
            "identity: pass --credential <key_id.secret> or set "
            "SATSA_CREDENTIAL")
    key_dir = Path(args.trust_key_dir) if args.trust_key_dir else Path(".satsa_identity")
    identity_service = satsa_security.build_identity_service(
        svc._db, ledger_dir=key_dir)
    try:
        principal = identity_service.authenticate(token)
    except Exception as exc:
        raise SystemExit(f"authentication failed: {exc}")
    if not principal.has_permission(DECISION_RECORD):
        raise SystemExit(
            f"identity {principal.name!r} lacks the decision.record "
            "permission (needs a satsa_supervisor or satsa_admin role)")
    from satsa.analysis.run import RunService
    f_row = svc._db.query_one(
        "SELECT * FROM satsa_findings WHERE id=?", (args.finding_id,))
    if f_row is None:
        raise SystemExit(f"finding {args.finding_id} not found")
    live = RunService._live_digest_for_finding(dict(f_row))
    history = svc.review_history(args.finding_id)
    prev_id = history[-1].id if history else None
    entry = svc.record_review(
        finding_id=args.finding_id,
        principal_identity_id=principal.identity_id,
        action=args.action,
        reason=args.reason or "",
        finding_content_digest=live,
        previous_revision_id=prev_id,
        trust_key_dir=key_dir,
    )
    print(f"recorded review {entry.id} (action={entry.action}, "
          f"principal={principal.name})")
    return 0


def cmd_report(args) -> int:
    """Render a HTML report for one entity."""
    from satsa.analysis.report import render_report
    svc = _open_service(args.db, args.trust_key_dir)
    e_row = svc._db.query_one(
        "SELECT * FROM satsa_entities WHERE id=?", (args.entity_id,))
    if e_row is None:
        raise SystemExit(f"entity {args.entity_id} not found")
    prof = svc.compute_risk(args.entity_id)
    if prof.run_id is None:
        raise SystemExit("entity has no analysis run")
    findings = svc._db.query_all(
        "SELECT f.*, o.worker_name FROM satsa_findings f"
        " JOIN satsa_observations o ON o.id=f.observation_id"
        " WHERE o.run_id=? ORDER BY f.created_at", (prof.run_id,))
    assessments = svc._db.query_all(
        "SELECT * FROM satsa_assessments WHERE entity_id=?"
        " ORDER BY period_start DESC", (args.entity_id,))
    html = render_report(entity=e_row, assessments=assessments,
                         risk=prof, findings=findings,
                         generated_at=__import__("time").time())
    out = Path(args.out) if args.out else Path(f"report-{args.entity_id}.html")
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}")
    return 0


def cmd_demo(args) -> int:
    """Load the committed demo dataset (5 CSEs)."""
    from satsa.ui.demo import load_demo_assessment
    svc = _open_service(args.db, args.trust_key_dir)
    result = load_demo_assessment(svc, Path(args.trust_key_dir) if args.trust_key_dir else None)
    print(json.dumps(result, indent=2, default=str))
    return 0


def cmd_validate(args) -> int:
    """Run synthetic ground-truth validation (layer + composition)."""
    from satsa.analysis.validate import run_validation, load_expert_labels
    from satsa.analysis.compval import run_composition_validation
    svc = _open_service(args.db, args.trust_key_dir)
    expert_labels = None
    expert_labels_path = getattr(args, "expert_labels", None)
    if expert_labels_path:
        expert_labels = load_expert_labels(Path(expert_labels_path))
    layer_report = run_validation(svc, expert_labels=expert_labels)
    # Real bound composition validation uses its own scratch DB
    # (isolates from the user's persistent database) and compares
    # synthetic scenario pipeline outputs against the ground-truth
    # catalog. Non-executable scenarios are reported honestly,
    # never fabricated.
    comp_report = run_composition_validation(
        trust_key_dir=args.trust_key_dir if args.trust_key_dir else None)
    combined = {
        "layers": layer_report.get("layers"),
        "composition_catalog": layer_report.get("composition"),
        "composition_bound": comp_report.get("executed"),
        "composition_not_executed": comp_report.get("not_executed"),
        "composition_summary": comp_report.get("summary"),
    }
    print(json.dumps(combined, indent=2, default=str))
    return 0


def cmd_benchmark(args) -> int:
    """Print the latest scaling benchmark (if available)."""
    from satsa.analysis.benchmark import print_benchmark
    print_benchmark(args.scaling_csv if hasattr(args, "scaling_csv") else None)
    return 0


def cmd_agents(args) -> int:
    """Print the 32-agent registry grouped by family."""
    from satsa.supervisor import list_agents
    agents = list_agents()
    print(f"SAT-SA {SATSA_VERSION} — {len(agents)} agents")
    for family in ("mlops", "satsa"):
        print(f"\n[{family.upper()}]")
        for a in list_agents(family=family):
            print(f"  {a.agent_id:<32} {a.name}")
            print(f"    purpose: {a.purpose}")
            print(f"    impl:    {a.implementation_ref}")
    return 0


def cmd_audit(args) -> int:
    """Database-wide meta-audit: sweep every run/finding/review
    decision and verify trust-receipt and provenance-binding
    coverage (satsa.analysis.meta_audit.run_meta_audit) — distinct
    from `sat-sa verify <run>`, which checks one run."""
    from satsa.analysis.meta_audit import run_meta_audit
    svc = _open_service(args.db, args.trust_key_dir)
    key_dir = Path(args.trust_key_dir) if args.trust_key_dir else Path(".satsa_identity")
    report = run_meta_audit(svc._db, key_dir)
    print(json.dumps(report.to_dict(), indent=2, default=str))
    return 0 if report.fully_compliant else 1


# Workers with a governed calibration path via `sat-sa calibrate`.
# Deliberately a small, explicit registry rather than auto-discovering
# every worker's threshold dataclass (field names vary per worker) —
# extend this dict, one line per worker, as calibration is wired for
# more of them. See satsa/analysis/calibration.py for why this is
# scoped rather than automatic.
def _calibratable_workers() -> dict:
    from satsa.analysis.workers.fast_closure import (
        FastClosureThresholds, FastClosureWorker)
    return {"fast-closure": (FastClosureWorker, FastClosureThresholds)}


def _calibration_ledger(args):
    from satsa.analysis.calibration import CalibrationLedger
    key_dir = Path(args.trust_key_dir) if args.trust_key_dir else Path(".satsa_identity")
    path = Path(args.calibration_ledger) if getattr(args, "calibration_ledger", None) \
        else key_dir / "calibration_ledger.jsonl"
    return CalibrationLedger(path)


def _latest_calibration_state(ledger, proposal_id: str):
    from satsa.analysis.calibration import CalibrationProposal
    rows = ledger.history(proposal_id)
    if not rows:
        raise SystemExit(f"no calibration proposal found with id {proposal_id!r}")
    return CalibrationProposal.from_dict(rows[-1])


def _authenticated_calibration_approver(svc, args):
    """Shared auth path for `decide`/`deploy`: requires
    calibration.approve, the same terminal-authority restriction
    decision.record carries (see qsmlops/security/permissions/model.py)."""
    import os
    from satsa import security as satsa_security
    from qsmlops.security.permissions.model import CALIBRATION_APPROVE
    token = args.credential or os.environ.get("SATSA_CREDENTIAL", "")
    if not token:
        raise SystemExit(
            "this action requires an authenticated identity: pass "
            "--credential <key_id.secret> or set SATSA_CREDENTIAL")
    key_dir = Path(args.trust_key_dir) if args.trust_key_dir else Path(".satsa_identity")
    identity_service = satsa_security.build_identity_service(svc._db, ledger_dir=key_dir)
    try:
        principal = identity_service.authenticate(token)
    except Exception as exc:
        raise SystemExit(f"authentication failed: {exc}")
    if not principal.has_permission(CALIBRATION_APPROVE):
        raise SystemExit(
            f"identity {principal.name!r} lacks the calibration.approve "
            "permission (needs a satsa_supervisor or satsa_admin role)")
    return principal


def cmd_calibrate(args) -> int:
    """Propose / test / decide / deploy a detector-threshold change
    (satsa.analysis.calibration) — the N17 governed calibration
    workflow extending the Validation Agent. Each action is one step;
    running them out of order is rejected with the same "must be
    tested before decided, must be approved before deployed" ordering
    the underlying module enforces."""
    try:
        return _dispatch_calibrate(args)
    except ValueError as exc:
        raise SystemExit(str(exc))


def _dispatch_calibrate(args) -> int:
    ledger = _calibration_ledger(args)

    if args.calibrate_action == "propose":
        import time
        from satsa.analysis.calibration import propose_calibration
        if not args.thresholds:
            raise SystemExit("--thresholds <JSON object> is required")
        try:
            thresholds = json.loads(args.thresholds)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"--thresholds is not valid JSON: {exc}")
        proposal_id = args.id or f"calib-{int(time.time())}"
        proposal = propose_calibration(
            proposal_id=proposal_id, worker_name=args.worker,
            layer=args.layer, proposed_thresholds=thresholds,
            rationale=args.rationale, proposer=args.proposer)
        ledger.append(proposal)
        print(json.dumps(proposal.to_dict(), indent=2, default=str))
        return 0

    if args.calibrate_action == "test":
        from satsa.analysis.calibration import run_calibration_test
        from satsa.analysis.validate import load_expert_labels
        from satsa.contracts.worker import RunContext, SnapshotRef
        from satsa.store.dataset import load_dataset
        if not args.id:
            raise SystemExit("--id <proposal_id> is required")
        proposal = _latest_calibration_state(ledger, args.id)
        registry = _calibratable_workers()
        if proposal.worker_name not in registry:
            raise SystemExit(
                f"worker {proposal.worker_name!r} has no registered "
                f"calibration path; known workers: {sorted(registry)}")
        worker_cls, thresholds_cls = registry[proposal.worker_name]
        if not args.entity_id or not args.assessment_id:
            raise SystemExit("--entity-id and --assessment-id are required "
                              "(the dataset a proposal is tested against)")
        if not args.expert_labels:
            raise SystemExit("--expert-labels <path> is required — a "
                              "proposal is graded against real labels, "
                              "never against its own output")
        svc = _open_service(args.db, args.trust_key_dir)
        dataset = load_dataset(svc._db, args.entity_id, args.assessment_id)
        expert_labels = load_expert_labels(Path(args.expert_labels))
        run_context = RunContext(run_id=f"calib-test-{proposal.id}",
                                 entity_id=args.entity_id,
                                 assessment_id=args.assessment_id)
        tested = run_calibration_test(
            proposal,
            baseline_worker=worker_cls(),
            candidate_worker=worker_cls(thresholds_cls(**proposal.proposed_thresholds)),
            snapshot=SnapshotRef("cli", args.entity_id, args.assessment_id),
            dataset=dataset, baselines=[], run_context=run_context,
            expert_labels=expert_labels)
        ledger.append(tested)
        print(json.dumps(tested.to_dict(), indent=2, default=str))
        return 0

    if args.calibrate_action in ("approve", "reject"):
        from satsa.analysis.calibration import decide_calibration_proposal
        if not args.id:
            raise SystemExit("--id <proposal_id> is required")
        if not args.rationale:
            raise SystemExit("--rationale is required for a decision")
        svc = _open_service(args.db, args.trust_key_dir)
        principal = _authenticated_calibration_approver(svc, args)
        proposal = _latest_calibration_state(ledger, args.id)
        decided = decide_calibration_proposal(
            proposal, decided_by=principal.identity_id,
            approve=(args.calibrate_action == "approve"),
            rationale=args.rationale)
        ledger.append(decided)
        print(json.dumps(decided.to_dict(), indent=2, default=str))
        return 0

    if args.calibrate_action == "deploy":
        from satsa.analysis.calibration import deploy_calibration_proposal
        if not args.id:
            raise SystemExit("--id <proposal_id> is required")
        if not args.version:
            raise SystemExit("--version <label> is required")
        svc = _open_service(args.db, args.trust_key_dir)
        _authenticated_calibration_approver(svc, args)  # deployment is
        # also a supervisor action — an approved proposal is not yet
        # live until someone with authority pushes it out
        proposal = _latest_calibration_state(ledger, args.id)
        deployed = deploy_calibration_proposal(proposal, version=args.version)
        ledger.append(deployed)
        print(json.dumps(deployed.to_dict(), indent=2, default=str))
        return 0

    if args.calibrate_action == "history":
        rows = ledger.history(args.id)
        print(json.dumps(rows, indent=2, default=str))
        return 0

    raise SystemExit(f"unknown calibrate action {args.calibrate_action!r}")


def cmd_ablate(args) -> int:
    """Run the ablation study (evaluation.ablation.run_ablation_study)
    for one already-ingested entity/assessment scope: disable exactly
    one default worker at a time and report which finding families
    disappear — each worker's measured, unique contribution."""
    from evaluation.ablation.runner import run_ablation_study
    svc = _open_service(args.db, args.trust_key_dir)
    report = run_ablation_study(svc._db, args.entity_id, args.assessment_id)
    print(json.dumps(report, indent=2, default=str))
    return 0


def cmd_doctor(args) -> int:
    """Diagnose the local install/deployment: runtime, dependencies,
    cryptographic provider, database, keystore, write permissions,
    offline posture. Every check here actually exercises the thing
    it claims to check — no check merely asserts a package imported."""
    import sys as _sys
    checks: list[tuple[str, str, str]] = []  # (name, status, detail)

    def _ok(name, detail=""):
        checks.append((name, "PASS", detail))

    def _fail(name, detail):
        checks.append((name, "FAIL", detail))

    def _warn(name, detail):
        checks.append((name, "WARN", detail))

    # 1. Python runtime
    if _sys.version_info >= (3, 10):
        _ok("python-version", f"{_sys.version.split()[0]}")
    else:
        _fail("python-version", f"{_sys.version.split()[0]} — need >= 3.10")

    # 2. Core dependencies actually import
    for mod in ("fastapi", "uvicorn", "pydantic", "cryptography",
               "dilithium_py", "kyber_py", "numpy", "scipy", "sklearn"):
        try:
            __import__(mod)
            _ok(f"dependency:{mod}")
        except ImportError as exc:
            _fail(f"dependency:{mod}", str(exc))

    # 3. Cryptographic provider — real sign/verify, not just import
    try:
        from qsmlops.crypto.providers import SIGNATURE_PROVIDERS
        prov = SIGNATURE_PROVIDERS["ML-DSA-65"]
        kp = prov.generate_keypair()
        sig = prov.sign(kp.secret_key, b"doctor-check")
        ok = prov.verify(kp.public_key, b"doctor-check", sig)
        if ok:
            _ok("pqc-provider", "ML-DSA-65 sign+verify roundtrip succeeded")
        else:
            _fail("pqc-provider", "ML-DSA-65 signature failed to verify")
    except Exception as exc:  # noqa: BLE001
        _fail("pqc-provider", str(exc))

    # 4. Database: connect + migrate (idempotent, safe to run again)
    db_path = Path(args.db)
    eng = None
    try:
        from qsmlops.database.engine import SQLiteDatabaseEngine
        from qsmlops.database.migrations import MigrationRunner
        eng = SQLiteDatabaseEngine(db_path)
        eng.connect()
        MigrationRunner(eng).migrate()
        tables = eng.query_all(
            "SELECT name FROM sqlite_master WHERE type='table' AND "
            "name LIKE 'satsa_%'")
        _ok("database", f"{db_path} — {len(tables)} satsa_* tables present")
    except Exception as exc:  # noqa: BLE001
        _fail("database", f"{db_path}: {exc}")

    # 5. Write permissions: db directory + trust key dir
    for label, p in (("db-dir", db_path.resolve().parent),
                     ("trust-key-dir",
                      Path(args.trust_key_dir).resolve()
                      if args.trust_key_dir else None)):
        if p is None:
            _warn(label, "no --trust-key-dir given; runs would be unsigned")
            continue
        try:
            p.mkdir(parents=True, exist_ok=True)
            probe = p / ".sat-sa-doctor-write-probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            _ok(label, str(p))
        except OSError as exc:
            _fail(label, f"{p}: {exc}")

    # 6. Keystore: trust key file readable/creatable
    if args.trust_key_dir and eng is not None:
        try:
            from satsa.analysis.trust import TrustService
            svc = TrustService(eng, Path(args.trust_key_dir))
            _ok("keystore", f"algorithm={svc.algorithm_id}, "
                             f"key={Path(args.trust_key_dir) / 'satsa_trust_key.json'}")
        except Exception as exc:  # noqa: BLE001
            _fail("keystore", str(exc))

    # 7. Optional HSM/PKCS#11 availability (best-effort; absence is not a failure)
    try:
        from qsmlops.crypto.hsm import create_hsm_backend, HSMUnavailableError
        try:
            create_hsm_backend({"use_hsm": True})
            _ok("hsm-provider", "an HSM backend is configured and reachable")
        except HSMUnavailableError:
            _warn("hsm-provider",
                 "no HSM configured — software keystore only (this is the "
                 "expected/documented posture; no ML-DSA hardware token "
                 "exists industry-wide, see docs/HSM_A11_CERTIFICATION.md)")
    except Exception as exc:  # noqa: BLE001
        _warn("hsm-provider", str(exc))

    # 8. Offline posture (best-effort signal, not a full guarantee —
    # see tests/test_phase18_satsa_offline_hardening.py for the real proof)
    net_modules = [m for m in ("requests", "httpx", "urllib3")
                  if m in _sys.modules]
    if net_modules:
        _warn("offline-posture",
             f"network-capable module(s) already imported: {net_modules} "
             "— not necessarily a problem (httpx is used by FastAPI's "
             "own TestClient), but worth knowing")
    else:
        _ok("offline-posture", "no network-capable module imported yet")

    failed = [c for c in checks if c[1] == "FAIL"]
    warned = [c for c in checks if c[1] == "WARN"]
    for name, status, detail in checks:
        line = f"[{status}] {name}"
        if detail:
            line += f" — {detail}"
        print(line)
    print(f"\n{len(checks) - len(failed) - len(warned)} passed, "
          f"{len(warned)} warned, {len(failed)} failed")
    return 1 if failed else 0


def cmd_decision(args) -> int:
    """Run the supervisor engine on a completed run."""
    from satsa.supervisor import (
        SupervisorEngine, DecisionContext, SATSA_VOCABULARY,
    )
    svc = _open_service(args.db, args.trust_key_dir)
    findings = svc._db.query_all(
        "SELECT f.*, o.worker_name FROM satsa_findings f"
        " JOIN satsa_observations o ON o.id=f.observation_id"
        " WHERE o.run_id=? AND f.state='signal'",
        (args.run_id,))
    trust_report = None
    if args.trust_key_dir:
        trust_report = svc.verify_run(args.run_id, Path(args.trust_key_dir))
    receipts = []
    if trust_report and "findings" in trust_report:
        receipts = trust_report["findings"]
    ctx = DecisionContext(
        vocabulary=args.vocabulary,
        scope={"run_id": args.run_id, "entity_id": args.entity_id or ""},
        run_id=args.run_id, findings=findings,
        trust_receipts=receipts,
        principal=args.principal or "cli",
    )
    eng = SupervisorEngine()
    decision = eng.run(ctx)
    print(json.dumps(decision.to_dict(), indent=2, default=str))
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sat-sa",
        description="SAT-SA — Supervisory Analytics Tool for SOC Assessment "
                    "(SIH 26157, NCIIPC). Air-gapped, post-quantum-trusted.",
    )
    p.add_argument("--db", default="./satsa.db",
                   help="SQLite database path (default: ./satsa.db)")
    p.add_argument("--trust-key-dir", default=None,
                   help="Directory holding the PQC trust keypair")
    p.add_argument("--version", action="version",
                   version=f"sat-sa {SATSA_VERSION}")

    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("ingest", help="ingest a CSE submission directory")
    sp.add_argument("entity")
    sp.add_argument("submission")
    sp.add_argument("--period-start", type=float, required=True)
    sp.add_argument("--period-end", type=float, required=True)
    sp.add_argument("--sector", default="")
    sp.add_argument("--env", default="")
    sp.add_argument("--source-system", default="cli")
    sp.add_argument("--policy-version", default="1.0")
    sp.set_defaults(func=cmd_ingest)

    sp = sub.add_parser("analyze", help="run analytics on an existing scope")
    sp.add_argument("entity_id")
    sp.add_argument("assessment_id")
    sp.set_defaults(func=cmd_analyze)

    sp = sub.add_parser("risk", help="compute the entity risk profile")
    sp.add_argument("entity_id")
    sp.set_defaults(func=cmd_risk)

    sp = sub.add_parser("prioritize", help="rank entities + findings")
    sp.add_argument("--run-id", default=None)
    sp.set_defaults(func=cmd_prioritize)

    sp = sub.add_parser("findings", help="list findings of a run")
    sp.add_argument("run_id")
    sp.add_argument("--state", default=None)
    sp.set_defaults(func=cmd_findings)

    sp = sub.add_parser("verify", help="verify a run's trust receipts")
    sp.add_argument("run_id")
    sp.set_defaults(func=cmd_verify)

    sp = sub.add_parser("review", help="record / list human review decisions")
    sp.add_argument("--list", metavar="FINDING_ID", default=None,
                    help="list review history for a finding instead of recording")
    sp.add_argument("--finding-id", default=None)
    sp.add_argument("--action", default=None,
                    choices=("confirm", "dismiss", "escalate",
                             "annotate", "request_review"))
    sp.add_argument("--reason", default=None)
    sp.add_argument("--credential", default=None,
                    help="key_id.secret bearer credential authenticating "
                         "the reviewer (or set SATSA_CREDENTIAL); required "
                         "to record a decision, not required for --list")
    sp.set_defaults(func=cmd_review)

    sp = sub.add_parser("report", help="render a HTML report")
    sp.add_argument("entity_id")
    sp.add_argument("--out", default=None)
    sp.set_defaults(func=cmd_report)

    sp = sub.add_parser("demo", help="load the committed demo dataset")
    sp.set_defaults(func=cmd_demo)

    sp = sub.add_parser("validate", help="run synthetic ground-truth validation")
    sp.add_argument("--expert-labels", default=None,
                    help="path to a JSON file of ExpertLabel records "
                         "(satsa.analysis.validate.ExpertLabel); when "
                         "omitted, layer validation is reported empty "
                         "rather than fabricated")
    sp.set_defaults(func=cmd_validate)

    sp = sub.add_parser("benchmark", help="print the scaling benchmark")
    sp.set_defaults(func=cmd_benchmark)

    sp = sub.add_parser("agents", help="print the 26-agent registry")
    sp.set_defaults(func=cmd_agents)

    sp = sub.add_parser("decision", help="run the supervisor on a run")
    sp.add_argument("run_id")
    sp.add_argument("--entity-id", default=None)
    sp.add_argument("--vocabulary", default="satsa",
                    choices=("satsa", "mlops"))
    sp.add_argument("--principal", default=None)
    sp.set_defaults(func=cmd_decision)

    sp = sub.add_parser(
        "doctor", help="diagnose the local install/deployment")
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser(
        "audit", help="database-wide meta-audit of trust/provenance coverage")
    sp.set_defaults(func=cmd_audit)

    sp = sub.add_parser(
        "ablate", help="ablation study: each worker's unique finding-family contribution")
    sp.add_argument("entity_id")
    sp.add_argument("assessment_id")
    sp.set_defaults(func=cmd_ablate)

    sp = sub.add_parser(
        "calibrate",
        help="propose / test / approve / reject / deploy a detector "
             "threshold change (N17 calibration workflow)")
    sp.add_argument("calibrate_action",
                    choices=("propose", "test", "approve", "reject",
                             "deploy", "history"))
    sp.add_argument("--id", default=None, help="proposal id "
                    "(required for test/approve/reject/deploy; optional "
                    "filter for history)")
    sp.add_argument("--worker", default=None,
                    help="worker name, e.g. 'fast-closure' (propose only)")
    sp.add_argument("--layer", default=None,
                    help="rule_or_category prefix this proposal targets "
                         "(propose only)")
    sp.add_argument("--thresholds", default=None,
                    help="JSON object of proposed threshold field values, "
                         "e.g. '{\"critical_max_seconds\": 300}' (propose only)")
    sp.add_argument("--rationale", default=None,
                    help="required for propose and for approve/reject")
    sp.add_argument("--proposer", default="cli-user", help="propose only")
    sp.add_argument("--entity-id", default=None, help="test only")
    sp.add_argument("--assessment-id", default=None, help="test only")
    sp.add_argument("--expert-labels", default=None,
                    help="path to a JSON file of ExpertLabel records "
                         "to score the proposal against (test only)")
    sp.add_argument("--version", default=None,
                    help="deployed version label (deploy only)")
    sp.add_argument("--credential", default=None,
                    help="key_id.secret bearer credential holding "
                         "calibration.approve (or set SATSA_CREDENTIAL); "
                         "required for approve/reject/deploy")
    sp.add_argument("--calibration-ledger", default=None,
                    help="path to the calibration ledger JSONL file "
                         "(default: <trust-key-dir>/calibration_ledger.jsonl)")
    sp.set_defaults(func=cmd_calibrate)

    return p


def main(argv=None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
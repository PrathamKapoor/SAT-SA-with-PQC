#!/usr/bin/env python3
"""SAT-SA end-to-end demonstration (SIH 26157).

One coherent story, mirroring the target architecture:

1. Open SAT-SA (build the service over a fresh offline database)
2. Show overview (entity roster)
3. Show the CSE requiring attention (highest risk)
4. Open the entity (risk decomposition — WHY)
5. Show evidence (Detect / Correlate / Assess findings)
6. Show the recommendation
7. Show TRUST-SAT verification (run + findings VERIFIED)
8. Human supervisor reviews (record a decision)
9. Decision becomes auditable (review history)
10. Show the architecture / agent layer (26 agents, supervisor decision)

Usage:
    python demo.py [--db ./demo-satsa.db] [--keys ./demo-keys]
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import time
from pathlib import Path


def _banner(n: int, title: str) -> None:
    print(f"\n{'=' * 64}\nSTEP {n}: {title}\n{'=' * 64}")


def main() -> int:
    ap = argparse.ArgumentParser(description="SAT-SA end-to-end demo")
    ap.add_argument("--db", default=None, help="SQLite path (default: temp)")
    ap.add_argument("--keys", default=None, help="trust key dir (default: temp)")
    args = ap.parse_args()

    tmpdir = None
    if args.db is None or args.keys is None:
        tmpdir = Path(tempfile.mkdtemp(prefix="satsa-demo-"))
    db_path = Path(args.db) if args.db else tmpdir / "satsa-demo.db"
    key_dir = Path(args.keys) if args.keys else tmpdir / "keys"

    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    from satsa.service import SatsaService
    from satsa.ui.demo import load_demo_assessment

    eng = SQLiteDatabaseEngine(db_path)
    eng.connect()
    MigrationRunner(eng).migrate()
    svc = SatsaService(eng)

    try:
        _banner(1, "Open SAT-SA — offline service over a fresh database")
        print(f"database : {db_path}")
        print(f"keys     : {key_dir}")
        print("network  : none (air-gapped by design)")

        _banner(2, "Overview — ingest the 5-CSE demo + run full analytics")
        t0 = time.time()
        demo = load_demo_assessment(svc, key_dir)
        print(f"loaded {demo['loaded']} entities in {time.time() - t0:.1f}s")
        for r in demo["results"]:
            print(f"  {r['cse_id']:<12} risk={r['total_score']:5.1f} "
                  f"confidence={r['confidence_bucket']:<6} "
                  f"findings={r['findings']} status={r['run_status']}")

        _banner(3, "CSE requiring attention — highest risk first")
        top = demo["results"][0]
        print(f"  >> {top['cse_id']} (risk {top['total_score']:.1f})")
        print(f"  entity_id     : {top['entity_id']}")
        print(f"  assessment_id : {top['assessment_id']}")
        print(f"  run_id        : {top['run_id']}")

        _banner(4, "Open the entity — risk decomposition (WHY)")
        risk = svc.compute_risk(top["entity_id"])
        for d in risk.dimensions:
            if d.score > 0:
                print(f"  {d.name:<24} score={d.score:5.1f} "
                      f"weight={d.weight}")
                print(f"    {d.rationale[:110]}")

        _banner(5, "Evidence — Detect / Correlate / Assess findings")
        findings = eng.query_all(
            "SELECT f.*, o.worker_name FROM satsa_findings f "
            "JOIN satsa_observations o ON o.id=f.observation_id "
            "WHERE o.run_id=? AND f.state='signal' ORDER BY f.created_at",
            (top["run_id"],))
        for f in findings[:10]:
            print(f"  [{f['worker_name']:<28}] {f['rule_or_category']}")
            print(f"    {f['rationale'][:110]}")

        _banner(6, "Recommendation — bounded human-action hint")
        from satsa.analysis.recommend import recommend
        if findings:
            rec = recommend(dict(findings[0]))
            print(f"  action : {rec.action}")
            print(f"  reason : {rec.reason[:160]}")
            print(f"  note   : {rec.limitations[:110]}")

        _banner(7, "TRUST-SAT verification — run + findings VERIFIED")
        report = svc.verify_run(top["run_id"], key_dir)
        print(f"  run      : {'VERIFIED' if report['run']['ok'] else 'FAILED'}"
              f" ({report['run']['reason']})")
        ok_n = sum(1 for f in report["findings"] if f["ok"])
        print(f"  findings : {ok_n}/{len(report['findings'])} VERIFIED")
        print("  signature: ML-DSA-65 · digest: SHA3-256 · ledger: hash-chain")

        _banner(8, "Human supervisor reviews — the terminal authority")
        if findings:
            from satsa.analysis.run import RunService
            live = RunService._live_digest_for_finding(dict(findings[0]))
            entry = svc.record_review(
                finding_id=findings[0]["id"],
                principal_identity_id="demo-examiner",
                action="confirm", reason="demo: corroborated by evidence",
                finding_content_digest=live, previous_revision_id=None)
            print(f"  recorded decision {entry.id} (action=confirm)")

        _banner(9, "Decision becomes auditable — review history")
        if findings:
            for h in svc.review_history(findings[0]["id"]):
                print(f"  [{h.action}] by={h.principal_identity_id} "
                      f"at={h.occurred_at:.0f} reason={h.reason!r}")

        _banner(10, "Architecture / agent layer — 26 agents, one engine")
        from satsa.supervisor import list_agents
        agents = list_agents()
        print(f"  {len(agents)} agents "
              f"({len(list_agents(family='mlops'))} MLOps + "
              f"{len(list_agents(family='satsa'))} SAT-SA)")
        from satsa.supervisor import SupervisorEngine, DecisionContext
        sig = [dict(f) for f in findings]
        ctx = DecisionContext(vocabulary="satsa",
                              scope={"entity_id": top["entity_id"]},
                              run_id=top["run_id"], findings=sig,
                              principal="demo-examiner")
        dec = SupervisorEngine().run(ctx)
        print(f"  supervisor decision: {dec.action} "
              f"(requires_human={dec.requires_human})")
    finally:
        eng.close()
        if tmpdir is not None and args.db is None and args.keys is None:
            shutil.rmtree(tmpdir, ignore_errors=True)

    print("\n" + "=" * 64 + "\nDEMO COMPLETED SUCCESSFULLY\n" + "=" * 64)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

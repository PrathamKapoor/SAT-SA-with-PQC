"""Demo loader for the SAT-SA UI: ingest the committed demo
dataset (5 CSEs) and run the full default worker set on each.
Returns a summary dict the UI can use to point the operator at
the most interesting entity.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

DEMO_ROOT = Path(__file__).resolve().parents[2] / "docs" / "demo" / "submissions"


def load_demo_assessment(service, trust_key_dir: Optional[Path] = None) -> dict:
    """Ingest every CSE in the demo and run its analytics. Returns
    a small dict describing the resulting run-state so the UI can
    redirect to the most informative page."""
    if not DEMO_ROOT.exists():
        raise FileNotFoundError(
            f"demo dataset missing at {DEMO_ROOT}; run scripts/build_demo_dataset.py")
    results: list[dict] = []
    for cse_dir in sorted(DEMO_ROOT.iterdir()):
        if not cse_dir.is_dir():
            continue
        cse_id = cse_dir.name
        # idempotent re-registration: register_entity returns the
        # existing entity on a duplicate name, so this is safe to
        # call repeatedly.
        entity = service.register_entity(cse_id, sector="defence",
                                          environment_class="on-prem")
        a = service.open_assessment(entity.id, 1735689600.0, 1738281600.0)
        ingest = service.submit(a.id, cse_dir)
        run = service.run_analysis(
            entity.id, a.id,
            trust_key_dir=trust_key_dir)
        risk = service.compute_risk(entity.id)
        results.append({
            "cse_id": cse_id,
            "entity_id": entity.id,
            "assessment_id": a.id,
            "ingest_status": ingest.status,
            "run_id": run.run_id,
            "run_status": run.status,
            "total_score": risk.total_score,
            "confidence_bucket": risk.confidence_bucket,
            "findings": len(run.finding_ids),
        })
    # pick the entity with the highest total score to feature first
    results.sort(key=lambda r: r["total_score"], reverse=True)
    return {
        "loaded": len(results),
        "results": results,
        "run_id": results[0]["run_id"] if results else None,
        "entity_id": results[0]["entity_id"] if results else None,
    }

"""Ablation runner: disable exactly one default analytical worker at a
time on an already-ingested scope, and re-measure which finding
families disappear — a worker's unique, non-overlapping contribution
to detection coverage, measured directly rather than asserted from a
static table.

Uses ``satsa.analysis.run.RunService.run(..., workers=...)``'s
existing override parameter — no new execution path in ``satsa/``
itself, and no worker is modified to run this. Each ablation is a
fresh, real ``AnalysisRun`` against the same persisted dataset; this
module never fabricates a "what if" result.
"""
from __future__ import annotations

from dataclasses import dataclass

from satsa.analysis.run import (
    DEFAULT_FAST_CLOSURE_POLICY,
    RunService,
    _default_workers,
)


@dataclass
class AblationResult:
    worker_name: str
    full_families: list
    ablated_families: list
    lost_families: list        # families present with all workers, absent without this one
    unique_contribution: bool  # True iff lost_families is non-empty

    def to_dict(self) -> dict:
        return {
            "worker_name": self.worker_name,
            "full_families": list(self.full_families),
            "ablated_families": list(self.ablated_families),
            "lost_families": list(self.lost_families),
            "unique_contribution": self.unique_contribution,
        }


def _emitted_families(db, run_id: str) -> set:
    rows = db.query_all(
        "SELECT DISTINCT rule_or_category FROM satsa_findings"
        " WHERE state='signal' AND observation_id IN"
        " (SELECT id FROM satsa_observations WHERE run_id=?)", (run_id,))
    return {r["rule_or_category"] for r in rows}


def run_ablation_study(engine, entity_id: str, assessment_id: str) -> dict:
    """Run the full default worker set once (the coverage baseline),
    then once per worker with exactly that worker removed, all against
    the SAME already-ingested scope. Returns the full-set finding
    families plus, per worker, exactly which finding families
    disappear when it alone is removed.

    A worker with ``unique_contribution=False`` is not necessarily
    useless — it may simply have found nothing to say about this
    particular scope (e.g. DriftWorker with no prior-period data to
    compare against), or every family it can emit may also be emitted
    by another worker (overlapping coverage, not zero coverage). This
    function reports the measured fact — which families vanish — and
    leaves the interpretation to the caller rather than labeling a
    worker "useless" from one scope's ablation alone.
    """
    svc = RunService(engine)

    full_workers = _default_workers(DEFAULT_FAST_CLOSURE_POLICY)
    full_run = svc.run(entity_id, assessment_id, workers=full_workers)
    full_families = _emitted_families(svc._db, full_run.run_id)

    results = []
    for excluded in full_workers:
        reduced = [w for w in _default_workers(DEFAULT_FAST_CLOSURE_POLICY)
                  if w.name != excluded.name]
        run = svc.run(entity_id, assessment_id, workers=reduced)
        ablated_families = _emitted_families(svc._db, run.run_id)
        lost = sorted(full_families - ablated_families)
        results.append(AblationResult(
            worker_name=excluded.name,
            full_families=sorted(full_families),
            ablated_families=sorted(ablated_families),
            lost_families=lost,
            unique_contribution=bool(lost),
        ))

    return {
        "full_families": sorted(full_families),
        "workers": [r.to_dict() for r in results],
    }

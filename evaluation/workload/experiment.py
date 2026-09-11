"""Simulated workload-reduction / prioritization-lift experiment.

SIH26157's success criterion explicitly asks for solutions that
"preserve the quality of supervisory assurance currently obtained
through expert human examination" while helping "prioritise manual
review effort." This module builds the most direct, honest
operationalization of that claim available without real examiner
data: compare SAT-SA's actual, already-computed entity prioritization
(``satsa.analysis.prioritize.prioritize_entities``) against a
**measured** random/chronological-sampling baseline, on a population
where "genuinely problematic entity" is an independently-generated
label — not something read back out of what SAT-SA itself decided.

Independence (SIH prompt section 22 / this repo's P19 precedent): a
population entity is labeled "pathological" or "clean" by the
*generator configuration* used to build its synthetic submission
(``satsa.analysis.synth.GenConfig`` — fast-closure rate, missing-
investigation rate, etc.), before any detector or ranking ever runs.
The label is never derived from SAT-SA's own findings or priority
score. Everything here is explicitly synthetic; call it "simulated
workload reduction," never "analyst time saved" — no real examiner
has ever used this experiment's output.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path


# A genuinely bad operational profile: alerts closed fast without
# real investigation, missing investigations outright, poor
# remediation follow-through, weak escalation discipline.
PATHOLOGICAL_CONFIG = dict(
    fast_closure_rate=0.6, missing_investigation_rate=0.4,
    no_remediation_rate=0.4, escalation_rate=0.2, disposition_rate=0.5,
)
# A genuinely clean operational profile — the same deterministic
# "healthy" configuration validated in P19's negative-control test
# (tests/test_phase64_satsa_fresh_database_e2e.py): every critical/
# high alert escalated, every alert dispositioned, no fast closure,
# no missing investigation, no remediation gaps.
CLEAN_CONFIG = dict(
    fast_closure_rate=0.0, missing_investigation_rate=0.0,
    no_remediation_rate=0.0, escalation_rate=1.0, disposition_rate=1.0,
)


@dataclass
class WorkloadPopulation:
    entity_ids: list[str]
    pathological_entity_ids: set[str]  # ground truth, independent of SAT-SA
    n_entities: int
    n_pathological: int
    seed: int


def build_population(engine, *, n_entities: int, n_pathological: int,
                     seed: int, trust_key_dir: Path,
                     period_start: float = 1735689600.0,
                     period_end: float = 1738281600.0) -> WorkloadPopulation:
    """Generate ``n_entities`` synthetic CSEs (``n_pathological`` of
    them configured pathological, the rest clean), ingest and analyze
    every one into ``engine``. Which entities are pathological is
    decided by a seeded shuffle *before* any generation happens, and
    is never touched again after label assignment — SAT-SA never
    sees this list."""
    if n_pathological > n_entities:
        raise ValueError("n_pathological cannot exceed n_entities")
    from satsa.analysis.synth import GenConfig, generate
    from satsa.service import SatsaService

    rng = random.Random(seed)
    indices = list(range(n_entities))
    rng.shuffle(indices)
    pathological_indices = set(indices[:n_pathological])

    svc = SatsaService(engine)
    entity_ids: list[str] = []
    pathological_ids: set[str] = set()
    for i in range(n_entities):
        is_pathological = i in pathological_indices
        overrides = dict(PATHOLOGICAL_CONFIG if is_pathological else CLEAN_CONFIG)
        cfg = GenConfig(seed=seed * 1000 + i, num_cse=1,
                        num_alerts=25, num_cases=6, **overrides)
        outroot = Path(trust_key_dir).parent / f"workload-gen-{seed}-{i}"
        paths = generate(cfg, outroot)
        entity = svc.register_entity(f"CSE-WL-{seed}-{i:03d}", sector="defence")
        assessment = svc.open_assessment(entity.id, period_start, period_end)
        svc.submit(assessment.id, paths[0])
        svc.run_analysis(entity.id, assessment.id, trust_key_dir=trust_key_dir)
        entity_ids.append(entity.id)
        if is_pathological:
            pathological_ids.add(entity.id)

    return WorkloadPopulation(
        entity_ids=entity_ids, pathological_entity_ids=pathological_ids,
        n_entities=n_entities, n_pathological=n_pathological, seed=seed)


@dataclass
class WorkloadResult:
    """Every field here describes a *simulated* measurement against
    synthetically-labeled data — not a claim about real analyst
    behavior or real time savings."""
    n_entities: int
    n_pathological: int
    k_percentages: list[int]
    satsa_recall_at_k: dict = field(default_factory=dict)
    random_recall_at_k_mean: dict = field(default_factory=dict)
    lift_over_random: dict = field(default_factory=dict)
    satsa_review_volume_to_find_all: int = 0
    random_review_volume_to_find_all_mean: float = 0.0
    n_random_trials: int = 0
    label: str = "simulated_workload_reduction"

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "n_entities": self.n_entities,
            "n_pathological": self.n_pathological,
            "k_percentages": self.k_percentages,
            "satsa_recall_at_k": self.satsa_recall_at_k,
            "random_recall_at_k_mean": self.random_recall_at_k_mean,
            "lift_over_random": self.lift_over_random,
            "satsa_review_volume_to_find_all": self.satsa_review_volume_to_find_all,
            "random_review_volume_to_find_all_mean":
                self.random_review_volume_to_find_all_mean,
            "n_random_trials": self.n_random_trials,
        }


def _recall_at_k(ordered_ids: list[str], pathological: set[str], top_n: int) -> float:
    if not pathological:
        return 0.0
    found = sum(1 for eid in ordered_ids[:top_n] if eid in pathological)
    return found / len(pathological)


def _review_volume_to_find_all(ordered_ids: list[str], pathological: set[str]) -> int:
    """Rank position (1-indexed) of the last pathological entity in
    this ordering — how many entities must be reviewed, in this
    order, before every genuinely-pathological one has been seen."""
    if not pathological:
        return 0
    last_pos = 0
    for i, eid in enumerate(ordered_ids, start=1):
        if eid in pathological:
            last_pos = i
    return last_pos


def run_workload_experiment(
    engine, population: WorkloadPopulation, *,
    k_percentages: tuple[int, ...] = (10, 20, 50),
    n_random_trials: int = 200, rng_seed: int = 12345,
) -> WorkloadResult:
    """Compare SAT-SA's actual, already-computed entity prioritization
    against a *measured* (not assumed) random-order baseline, over
    ``n_random_trials`` independent shuffles of the same population."""
    from satsa.analysis.prioritize import prioritize_entities

    ranked = prioritize_entities(engine)
    ranked_ids = [p.entity_id for p in ranked if p.entity_id in set(population.entity_ids)]
    # Every population entity must appear in the ranking — if not,
    # prioritize_entities() silently dropped one, which is itself a
    # real defect this experiment would need to surface, not hide.
    missing = set(population.entity_ids) - set(ranked_ids)
    if missing:
        raise AssertionError(
            f"{len(missing)} population entities never appeared in "
            f"prioritize_entities() output: {sorted(missing)[:5]}")

    n = population.n_entities
    result = WorkloadResult(
        n_entities=n, n_pathological=population.n_pathological,
        k_percentages=list(k_percentages), n_random_trials=n_random_trials)

    rng = random.Random(rng_seed)
    random_trials: dict[int, list[float]] = {k: [] for k in k_percentages}
    random_volumes: list[int] = []
    for _ in range(n_random_trials):
        shuffled = list(population.entity_ids)
        rng.shuffle(shuffled)
        for k in k_percentages:
            top_n = max(1, round(n * k / 100))
            random_trials[k].append(
                _recall_at_k(shuffled, population.pathological_entity_ids, top_n))
        random_volumes.append(
            _review_volume_to_find_all(shuffled, population.pathological_entity_ids))

    for k in k_percentages:
        top_n = max(1, round(n * k / 100))
        satsa_r = _recall_at_k(ranked_ids, population.pathological_entity_ids, top_n)
        random_r = sum(random_trials[k]) / len(random_trials[k])
        result.satsa_recall_at_k[k] = round(satsa_r, 4)
        result.random_recall_at_k_mean[k] = round(random_r, 4)
        result.lift_over_random[k] = (
            round(satsa_r / random_r, 3) if random_r > 0 else
            (float("inf") if satsa_r > 0 else 1.0))

    result.satsa_review_volume_to_find_all = _review_volume_to_find_all(
        ranked_ids, population.pathological_entity_ids)
    result.random_review_volume_to_find_all_mean = round(
        sum(random_volumes) / len(random_volumes), 2)

    return result

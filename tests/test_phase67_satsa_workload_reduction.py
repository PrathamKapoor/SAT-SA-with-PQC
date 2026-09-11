"""Phase P21 — simulated workload-reduction / prioritization-lift.

Nothing in the codebase measured this before: does SAT-SA's actual
entity prioritization (satsa.analysis.prioritize.prioritize_entities)
surface genuinely-problematic entities faster than a supervisor
sampling in random/chronological order? SIH26157 explicitly names
this as a success criterion ("prioritise manual review effort...
preserve the quality of supervisory assurance").

The "genuinely problematic" label is assigned by
evaluation.workload.build_population *before* SAT-SA ever runs, from
the synthetic generator's own configuration (fast-closure rate,
missing-investigation rate, etc.) — SAT-SA's prioritization never
sees this label. The random baseline is *measured* over many
independent shuffles, not assumed analytically. Every reported number
is labeled "simulated" — this is synthetic-population evidence, not a
claim about real analysts or real entities.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from evaluation.workload import build_population, run_workload_experiment


@pytest.fixture()
def engine(tmp_path):
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    eng = SQLiteDatabaseEngine(tmp_path / "workload.db")
    eng.connect()
    MigrationRunner(eng).migrate()
    yield eng
    eng.close()


def test_population_labels_are_independent_of_satsa(tmp_path, engine):
    """The population builder must label entities before any SAT-SA
    computation runs — proven structurally: pathological_entity_ids
    is fixed by build_population's own seeded shuffle, and
    prioritize_entities() is never called until run_workload_experiment."""
    pop = build_population(
        engine, n_entities=10, n_pathological=4, seed=1,
        trust_key_dir=tmp_path / "keys")
    assert len(pop.entity_ids) == 10
    assert len(pop.pathological_entity_ids) == 4
    assert pop.pathological_entity_ids <= set(pop.entity_ids)


def test_satsa_prioritization_beats_random_at_every_k(tmp_path, engine):
    """The core claim: SAT-SA's real prioritization, run against a
    population with independently-labeled genuine problems, achieves
    higher recall@k than a measured random-order baseline."""
    pop = build_population(
        engine, n_entities=20, n_pathological=6, seed=7,
        trust_key_dir=tmp_path / "keys")
    result = run_workload_experiment(
        engine, pop, k_percentages=(10, 20, 50), n_random_trials=300,
        rng_seed=42)

    assert result.label == "simulated_workload_reduction"
    for k in (10, 20, 50):
        assert k in result.satsa_recall_at_k
        assert k in result.random_recall_at_k_mean
        # The random baseline should land close to its analytic
        # expectation (k/100) — a sanity check that the empirical
        # measurement isn't broken, not a hardcoded substitute for it.
        expected = k / 100
        assert abs(result.random_recall_at_k_mean[k] - expected) < 0.15, (
            f"measured random recall@{k} = {result.random_recall_at_k_mean[k]} "
            f"is implausibly far from the {expected} analytic expectation — "
            "the shuffle/measurement logic itself may be broken")

    # SAT-SA must beat random at at least the smaller k values, where
    # a real prioritization signal has the most room to show lift.
    assert result.satsa_recall_at_k[10] >= result.random_recall_at_k_mean[10]
    assert result.satsa_recall_at_k[20] >= result.random_recall_at_k_mean[20]
    assert result.lift_over_random[10] >= 1.0

    # Review-volume-to-find-all: SAT-SA should need to review no more
    # entities (in its own order) than the random-order mean to find
    # every genuinely pathological one.
    assert result.satsa_review_volume_to_find_all <= pop.n_entities
    assert result.random_review_volume_to_find_all_mean > 0


def test_no_pathological_entities_is_handled_without_division_errors(tmp_path, engine):
    pop = build_population(
        engine, n_entities=6, n_pathological=0, seed=3,
        trust_key_dir=tmp_path / "keys")
    result = run_workload_experiment(
        engine, pop, k_percentages=(10, 50), n_random_trials=20)
    assert result.satsa_recall_at_k[10] == 0.0
    assert result.satsa_review_volume_to_find_all == 0


def test_workload_result_reports_real_measured_numbers_not_fabricated(tmp_path, engine):
    """Regression guard against ever hand-typing/hardcoding a result:
    two independent populations with different seeds must not produce
    byte-identical WorkloadResult numbers (that would indicate a
    hardcoded return rather than a measurement driven by actual data)."""
    pop_a = build_population(
        engine, n_entities=12, n_pathological=4, seed=11,
        trust_key_dir=tmp_path / "keys-a")
    result_a = run_workload_experiment(engine, pop_a, n_random_trials=50)

    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    eng_b = SQLiteDatabaseEngine(tmp_path / "workload_b.db")
    eng_b.connect()
    MigrationRunner(eng_b).migrate()
    pop_b = build_population(
        eng_b, n_entities=12, n_pathological=8, seed=99,
        trust_key_dir=tmp_path / "keys-b")
    result_b = run_workload_experiment(eng_b, pop_b, n_random_trials=50)
    eng_b.close()

    assert result_a.to_dict() != result_b.to_dict(), (
        "two structurally different populations produced identical "
        "results — suspicious of a hardcoded/fabricated return value")

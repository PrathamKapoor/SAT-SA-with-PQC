from __future__ import annotations

import pytest

from evaluation.workload import build_population, run_workload_experiment


@pytest.fixture
def engine(tmp_path):
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner

    db = SQLiteDatabaseEngine(tmp_path / "research-workload.sqlite3")
    db.connect()
    MigrationRunner(db).migrate()
    yield db
    db.close()


def test_randomization_raw_samples_and_descriptive_distribution(engine, tmp_path):
    population = build_population(
        engine, n_entities=4, n_pathological=2, seed=89, trust_key_dir=tmp_path / "keys"
    )
    result = run_workload_experiment(
        engine, population, k_percentages=(25, 50), n_random_trials=5, rng_seed=99
    )

    assert set(result.random_recall_at_k_trials) == {25, 50}
    for k in (25, 50):
        assert len(result.random_recall_at_k_trials[k]) == 5
        summary = result.random_recall_at_k_distribution[k]
        assert summary["n"] == 5
        assert summary["minimum"] <= summary["median"] <= summary["maximum"]
        assert summary["interpretation"].endswith("not a confidence interval")
    assert len(result.random_review_volume_to_find_all_trials) == 5
    assert (
        result.to_dict()["random_recall_at_k_trials"]
        == result.random_recall_at_k_trials
    )


def test_workload_experiment_rejects_zero_random_trials(engine):
    from evaluation.workload.experiment import WorkloadPopulation

    population = WorkloadPopulation(["e1"], {"e1"}, 1, 1, 1)
    with pytest.raises(ValueError, match="n_random_trials"):
        run_workload_experiment(engine, population, n_random_trials=0)

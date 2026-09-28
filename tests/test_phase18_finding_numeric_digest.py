"""A finding's digest must equal the digest recomputed from its stored row.

Found by the Phase 18 browser end-to-end test: the metric-gaming worker
emitted an int statistic (statistics.mean over step counts), the digest was
taken over `1`, the REAL column read back `1.0`, and the supervisory decision
failed with "finding digest mismatch".
"""

from qsmlops.crypto.hashing import digest_document
from qsmlops.database.engine import create_engine
from qsmlops.database.migrations import MigrationRunner
from satsa.analysis.canonical import (
    canonical_finding_dict_from_row,
    live_finding_digest,
)
from satsa.domain.evidence import ConfidenceVector, Finding


def test_integer_numeric_fields_are_normalized_to_float():
    f = Finding(
        observation_id="obs_1",
        rule_or_category="r",
        state="no_signal",
        statistic=1,
        effect=0,
        threshold=2,
    )
    assert (f.statistic, f.effect, f.threshold) == (1.0, 0.0, 2.0)
    assert all(isinstance(v, float) for v in (f.statistic, f.effect, f.threshold))
    assert (
        Finding(observation_id="o", rule_or_category="r", state="no_signal").statistic
        is None
    )


def test_digest_survives_a_real_column_round_trip(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'digest.db').as_posix()}")
    MigrationRunner(engine).migrate()
    finding = Finding(
        observation_id="obs_1",
        rule_or_category="execution_gap.potential_metric_gaming",
        state="signal",
        statistic=1,
        effect=2 / 3,
        threshold=1.5,
        confidence=ConfidenceVector(
            analytical_support=2 / 3, evidence_completeness=0.25
        ),
        evidence_refs=["srcrec_1"],
    )
    engine.execute(
        "CREATE TABLE probe (statistic REAL, effect REAL, threshold REAL)",
    )
    engine.execute(
        "INSERT INTO probe VALUES (?,?,?)",
        (finding.statistic, finding.effect, finding.threshold),
    )
    stored = engine.query_one("SELECT statistic, effect, threshold FROM probe")
    row = {
        "id": finding.id,
        "observation_id": finding.observation_id,
        "rule_or_category": finding.rule_or_category,
        "state": finding.state,
        "rationale": finding.rationale,
        "limitations": finding.limitations,
        "scoped_subjects_json": "[]",
        "evidence_refs_json": '["srcrec_1"]',
        "confidence_json": __import__("json").dumps(finding.confidence.to_dict()),
        **stored,
    }
    assert canonical_finding_dict_from_row(row) == finding.to_dict()
    assert live_finding_digest(row) == digest_document(finding.to_dict())

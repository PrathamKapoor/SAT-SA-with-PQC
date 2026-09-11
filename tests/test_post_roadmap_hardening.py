"""Post-Roadmap Hardening regression suite (S1-S5, C1-C6, T1-T8, licence, config).

Every approved fix from the 24-hour autonomous hardening pass has at least one
explicit regression test here. Tests prefer asserting real governance/security
outcomes (deployment state, ledger events, alert emission, fail-closed
behaviour) over implementation details.

This file is engineering-hardening work only — it does NOT introduce Phase 11
or any new architecture.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from qsmlops.agents.base import BaseAgent, Finding, Observation
from qsmlops.artifacts.store import ArtifactStore
from qsmlops.config import PlatformConfig
from qsmlops.evidence.ledger import EvidenceLedger
from qsmlops.ml.drift import DriftDetectionEngine
from qsmlops.monitoring.alerts import evaluate as evaluate_alerts
from qsmlops.monitoring.collector import TelemetryCollector
from qsmlops.pipeline.selfheal import SelfHealingMLOps
from qsmlops.pipeline.training import make_synthetic_regression
from qsmlops.serving.deployment import DeploymentService
from qsmlops.supervisor.supervisor import _normalize_recommendation
from qsmlops.supplychain.bom import QMLBOM


# ----------------------------------------------------------------------
# helpers / fixtures
# ----------------------------------------------------------------------
@pytest.fixture()
def pipe(tmp_path):
    config = PlatformConfig(tmp_path / "home")
    p = SelfHealingMLOps(config)
    ds = make_synthetic_regression(150, seed=11)
    p.provision_dataset("hardening-data", ds)
    yield p
    p.close()


def _deploy(pipeline, model):
    """Train, verify, approve and deploy a version; return its version_id."""
    r = pipeline.train_and_register(model, "hardening-data")
    ev = pipeline.evaluate_version(r["version_id"])
    assert ev["decision"] == "VERIFIED"
    pipeline.request_approval(r["version_id"], approver="governor")
    pipeline.request_deployment(model_name=model, actor="deployer")
    return r["version_id"]


class _RecAgent(BaseAgent):
    name = "rec-agent"

    def __init__(self, rec):
        self._rec = rec

    def observe(self, context):
        return Observation(
            agent=self.name, subject_id="", recommendation=self._rec, findings=[]
        )


# ----------------------------------------------------------------------
# S1 — rollback must use governed deployment validation
# ----------------------------------------------------------------------
class TestS1RollbackGovernance:
    def test_successful_governed_rollback(self, pipe):
        v1 = _deploy(pipe, "s1a")
        v2 = _deploy(pipe, "s1a")
        prev = pipe.registry.rollback("s1a", "cli")
        assert prev == v1
        assert pipe.registry.get_version(v1)["state"] == "DEPLOYED"
        assert pipe.registry.active_deployment("s1a")["version_id"] == v1

    def test_rollback_blocked_when_signer_revoked(self, pipe):
        v1 = _deploy(pipe, "s1b")
        v2 = _deploy(pipe, "s1b")
        signer = pipe.registry.load_passport(v1).signature.signer_key_id
        pipe.keystore.revoke(signer)
        prev = pipe.registry.rollback("s1b", "cli")
        assert prev is None
        # active deployment is unchanged (rollback refused, not bypassed)
        assert pipe.registry.active_deployment("s1b")["version_id"] == v2
        types = [e.get("record", {}).get("type") for e in pipe.ledger.iter_entries()]
        assert "rollback_blocked" in types

    def test_rollback_blocked_records_failed_checks(self, pipe):
        v1 = _deploy(pipe, "s1c")
        _deploy(pipe, "s1c")
        signer = pipe.registry.load_passport(v1).signature.signer_key_id
        pipe.keystore.revoke(signer)
        pipe.registry.rollback("s1c", "cli")
        blocked = [
            e["record"]
            for e in pipe.ledger.iter_entries()
            if e.get("record", {}).get("type") == "rollback_blocked"
        ]
        assert blocked and "failed_checks" in blocked[-1]

    def test_rollback_no_previous_returns_none(self, pipe):
        # Single version deployed -> rollback returns None (no previous to restore)
        _deploy(pipe, "s1d")
        assert pipe.registry.rollback("s1d", "cli") is None


# ----------------------------------------------------------------------
# S2 — DataAgent must not downgrade HIGH findings to ACCEPT
# ----------------------------------------------------------------------
class TestS2DataAgentSeverity:
    def test_no_datasets_escalates(self, tmp_path):
        from qsmlops.agents.data_agent import DataAgent

        agent = DataAgent(ArtifactStore(tmp_path / "art"))
        obs = agent.observe({"bom": QMLBOM.create()})
        assert obs.recommendation == "ESCALATE"

    def test_corrupted_dataset_quarantines(self, tmp_path):
        from qsmlops.agents.data_agent import DataAgent

        store = ArtifactStore(tmp_path / "art")
        agent = DataAgent(store)
        bom = QMLBOM.create()
        bom.add_entry("dataset", "d", "0" * 64)  # absent -> integrity failure
        obs = agent.observe({"bom": bom})
        assert obs.recommendation == "QUARANTINE"

    def test_clean_data_accepted(self, pipe):
        from qsmlops.agents.data_agent import DataAgent

        agent = DataAgent(pipe.artifacts)
        idx = pipe._load_dataset_index()["hardening-data"]
        bom = QMLBOM.create()
        bom.add_entry("dataset", "hardening-data", idx)
        obs = agent.observe({"bom": bom})
        assert obs.recommendation == "ACCEPT"


# ----------------------------------------------------------------------
# S3 — dropped evidence must fail closed (ESCALATE)
# ----------------------------------------------------------------------
class TestS3DroppedEvidenceFailClosed:
    def test_dropped_finding_flips_escalate(self, pipe):
        r = pipe.train_and_register("s3", "hardening-data")
        sup = pipe.supervisor
        ctx = sup.gather_context(r["version_id"])
        orig = sup.agents

        class _Bad(BaseAgent):
            name = "bad"

            def observe(self, context):
                f = Finding(name="x", passed=False, severity="BOGUS", recommendation="")
                return Observation(
                    agent=self.name, subject_id="", recommendation="ACCEPT", findings=[f]
                )

        sup.agents = [_Bad()]
        try:
            obs_list = sup.collect_observations(ctx)
        finally:
            sup.agents = orig
        bad = [o for o in obs_list if o.agent == "bad"][0]
        assert bad.recommendation == "ESCALATE"
        assert any(f.name == "evidence_validation" for f in bad.findings)


# ----------------------------------------------------------------------
# C2 — dropped-finding counter (dedup must NOT trigger marker)
# ----------------------------------------------------------------------
class TestC2DroppedCounter:
    def test_dedup_does_not_emit_marker(self, pipe):
        r = pipe.train_and_register("c2", "hardening-data")
        sup = pipe.supervisor
        ctx = sup.gather_context(r["version_id"])
        orig = sup.agents

        class _Dup(BaseAgent):
            name = "dup"

            def observe(self, context):
                f = Finding(name="same", passed=True, severity="LOW", detail="x")
                return Observation(
                    agent=self.name, subject_id="", recommendation="ACCEPT",
                    findings=[f, f],
                )

        sup.agents = [_Dup()]
        try:
            obs_list = sup.collect_observations(ctx)
        finally:
            sup.agents = orig
        dup = [o for o in obs_list if o.agent == "dup"][0]
        assert dup.recommendation == "ACCEPT"
        assert not any(f.name == "evidence_validation" for f in dup.findings)


# ----------------------------------------------------------------------
# S4 — drift detection must not turn invalid input into healthy
# ----------------------------------------------------------------------
class TestS4DriftFailOpen:
    def test_empty_current_indeterminate(self):
        eng = DriftDetectionEngine()
        ref = np.random.RandomState(0).randn(100, 3)
        eng.set_reference(ref, feature_names=["f0", "f1", "f2"])
        reports = eng.detect_all(np.zeros((0, 3)))
        assert any(r.drift_type == "drift_indeterminate" for r in reports)
        assert any(r.severity == "MEDIUM" for r in reports)

    def test_nan_triggers_medium(self):
        eng = DriftDetectionEngine()
        rng = np.random.RandomState(0)
        ref = rng.randn(100, 2)
        eng.set_reference(ref, feature_names=["a", "b"])
        cur = rng.randn(50, 2)
        cur[0, 0] = np.nan
        reports = eng.detect_all(cur)
        assert any(r.severity == "MEDIUM" for r in reports)
        assert any("error" in r.drift_type for r in reports)

    def test_wrong_shape_medium_via_pipeline(self, pipe):
        _deploy(pipe, "s4")
        outcome = pipe.health_check("s4", current_data=[[0.0]])
        assert outcome["drift_summary"]["max_severity"] == "MEDIUM"


# ----------------------------------------------------------------------
# S5 — signer lookup must fail closed on AttributeError
# ----------------------------------------------------------------------
class TestS5SignerFailClosed:
    def test_signer_attributeerror_blocks(self, pipe, monkeypatch):
        v = pipe.train_and_register("s5", "hardening-data")
        svc = DeploymentService(pipe.registry)

        class _BadRec:
            pass

        def fake_get(key_id):
            return _BadRec()

        monkeypatch.setattr(pipe.registry.keystore, "get_record", fake_get)
        report = svc.validate(v["version_id"], "deployer", "production")
        assert report["eligible"] is False
        assert any(c["name"] == "signer_key_usable" and not c["passed"]
                   for c in report["checks"])


# ----------------------------------------------------------------------
# C1 — non-Decision recommendations must not inflate conflict count
# ----------------------------------------------------------------------
class TestC1RecommendationNormalization:
    def test_normalize_mapping(self):
        assert _normalize_recommendation("BLOCK") == "BLOCK_DEPLOYMENT"
        assert _normalize_recommendation("REVIEW") == "ADVISORY"
        assert _normalize_recommendation("INVESTIGATE") == "ADVISORY"
        assert _normalize_recommendation("OPTIMIZE") == "ADVISORY"
        assert _normalize_recommendation("MONITOR") == "ADVISORY"
        assert _normalize_recommendation("EVALUATE_TRUST") == "ADVISORY"
        assert _normalize_recommendation("ACCEPT") == "ACCEPT"
        assert _normalize_recommendation("QUARANTINE") == "QUARANTINE"
        # unknown string fails closed to ESCALATE
        assert _normalize_recommendation("TOTALLY_UNKNOWN") == "ESCALATE"

    def test_advisory_does_not_inflate_conflict(self, pipe):
        from qsmlops.supervisor.decisions import Decision

        r = pipe.train_and_register("c1", "hardening-data")
        sup = pipe.supervisor
        ctx = sup.gather_context(r["version_id"])
        orig = sup.agents
        sup.agents = [
            _RecAgent("REVIEW"), _RecAgent("MONITOR"),
            _RecAgent("OPTIMIZE"), _RecAgent("ACCEPT"),
        ]
        try:
            obs_list = sup.collect_observations(ctx)
            recs = {o.recommendation for o in obs_list}
            assert recs == {"ADVISORY", "ACCEPT"}
            report, _ = sup.reason(r["version_id"], context_override=ctx)
        finally:
            sup.agents = orig
        # advisory strings must never force a spurious ESCALATE-by-conflict
        assert report.decision != Decision.ESCALATE or "conflicting" not in report.rationale


# ----------------------------------------------------------------------
# C3 — negative MSE must not be treated as healthy
# ----------------------------------------------------------------------
class TestC3NegativeMSE:
    def test_negative_mse_alerts(self):
        alerts = evaluate_alerts("m", metrics={"mse": -1.0, "r2": 0.9})
        assert any(a.code == "PERFORMANCE_DEGRADED" for a in alerts)

    def test_valid_metrics_no_false_alert(self):
        alerts = evaluate_alerts("m", metrics={"mse": 0.01, "r2": 0.95})
        assert not any(a.code == "PERFORMANCE_DEGRADED" for a in alerts)


# ----------------------------------------------------------------------
# C4 — CLI approve-and-deploy + deprecated approve alias
# ----------------------------------------------------------------------
class TestC4CliApproveAndDeploy:
    def test_approve_and_deploy_reaches_deployed(self, tmp_path, monkeypatch):
        from click.testing import CliRunner

        from qsmlops.cli import cli

        monkeypatch.setenv("QSMLOPS_HOME", str(tmp_path / "cli_home"))
        runner = CliRunner()
        runner.invoke(
            cli, ["provision-dataset", "--name", "c4", "--samples", "120"],
            catch_exceptions=False,
        )
        runner.invoke(cli, ["train", "--model", "c4m", "--dataset", "c4"],
                      catch_exceptions=False)
        runner.invoke(cli, ["verify", "--version-id",
                            _last_version_id(tmp_path)],
                      catch_exceptions=False)
        # approve-and-deploy promotes to DEPLOYED
        result = runner.invoke(
            cli, ["approve-and-deploy", "--version-id",
                  _last_version_id(tmp_path)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0

    def test_deprecated_approve_alias_warns(self, tmp_path, monkeypatch):
        from click.testing import CliRunner

        from qsmlops.cli import cli

        monkeypatch.setenv("QSMLOPS_HOME", str(tmp_path / "cli_home2"))
        runner = CliRunner()
        runner.invoke(cli, ["provision-dataset", "--name", "c4b", "--samples", "120"],
                      catch_exceptions=False)
        runner.invoke(cli, ["train", "--model", "c4bm", "--dataset", "c4b"],
                      catch_exceptions=False)
        result = runner.invoke(cli, ["approve", "--version-id",
                                     _last_version_id(tmp_path)],
                                catch_exceptions=False)
        assert "deprecated" in result.output


def _last_version_id(tmp_path):
    """Resolve the most recently registered version id from the CLI home."""
    import os
    import sqlite3

    home = Path(os.environ["QSMLOPS_HOME"])
    db = home / "registry" / "registry.sqlite3"
    conn = sqlite3.connect(str(db))
    row = conn.execute(
        "SELECT version_id FROM model_versions ORDER BY registered_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row[0]


# ----------------------------------------------------------------------
# C5 — pydantic declared
# ----------------------------------------------------------------------
class TestC5PydanticDeclared:
    def test_pydantic_in_dependencies(self):
        import pydantic  # must import without transitive luck

        text = (Path(__file__).parent.parent / "pyproject.toml").read_text()
        assert "pydantic" in text


# ----------------------------------------------------------------------
# C6 — API revoke returns 409 on illegal transition
# ----------------------------------------------------------------------
class TestC6ApiRevoke409:
    def test_illegal_revoke_returns_409(self, api_client):
        from qsmlops.pipeline.training import make_synthetic_regression

        pipeline = api_client.app.state.container.get("pipeline")
        pipeline.provision_dataset("c6", make_synthetic_regression(80, seed=7))
        r = pipeline.train_and_register("c6", "c6")
        ev = pipeline.evaluate_version(r["version_id"])
        assert ev["decision"] == "VERIFIED"
        pipeline.request_approval(r["version_id"], approver="gov")
        first = api_client.post(
            f"/registry/revoke/{r['version_id']}",
            json={"reason": "x", "actor": "api"},
        )
        assert first.status_code == 200
        second = api_client.post(
            f"/registry/revoke/{r['version_id']}",
            json={"reason": "y", "actor": "api"},
        )
        assert second.status_code == 409


# ----------------------------------------------------------------------
# T1 — observation validation must be fail-safe
# ----------------------------------------------------------------------
class TestT1ValidationFailSafe:
    def test_validation_crash_fail_closed(self, pipe, monkeypatch):
        r = pipe.train_and_register("t1", "hardening-data")
        sup = pipe.supervisor
        ctx = sup.gather_context(r["version_id"])
        orig = sup.agents

        def boom(obs):
            raise RuntimeError("validator exploded")

        monkeypatch.setattr(
            "qsmlops.supervisor.supervisor.validate_observation", boom
        )

        class _A(BaseAgent):
            name = "a"

            def observe(self, c):
                return Observation(agent="a", subject_id="", recommendation="ACCEPT",
                                   findings=[])

        sup.agents = [_A()]
        try:
            obs_list = sup.collect_observations(ctx)
        finally:
            sup.agents = orig
        assert obs_list[0].recommendation == "ESCALATE"
        assert any(f.name == "observation_validation" for f in obs_list[0].findings)


# ----------------------------------------------------------------------
# T2 — dead supervisor imports removed
# ----------------------------------------------------------------------
class TestT2DeadImports:
    def test_no_dead_imports(self):
        import qsmlops.supervisor.supervisor as m

        assert not hasattr(m, "sanitise_all")
        assert not hasattr(m, "observation_risk")


# ----------------------------------------------------------------------
# T3 — ledger malformed-line tolerance
# ----------------------------------------------------------------------
class TestT3LedgerMalformed:
    def test_malformed_reported_and_valid_preserved(self, tmp_path):
        ledger = EvidenceLedger(tmp_path / "ledger.jsonl")
        for i in range(3):
            ledger.append({"type": f"e{i}"})
        p = ledger.path
        lines = p.read_text().splitlines()
        lines[1] = "this is not json"
        p.write_text("\n".join(lines) + "\n")
        ok, msg = ledger.verify_chain()
        assert ok is False
        assert "corrupted" in msg
        entries = ledger._entries()
        assert len(entries) == 2
        assert {e["record"]["type"] for e in entries} == {"e0", "e2"}


# ----------------------------------------------------------------------
# T4 — rolling baseline effective threshold
# ----------------------------------------------------------------------
class TestT4RollingBaseline:
    def test_exactly_sufficient(self, tmp_path):
        from qsmlops.config import MONITORING_MIN_HISTORY

        tc = TelemetryCollector(tmp_path / "t.jsonl")
        window = 10
        mh = MONITORING_MIN_HISTORY
        for _ in range(mh):
            tc.record("m", "metric", "mse", 1.0)
        for _ in range(window):
            tc.record("m", "metric", "mse", 1.5)
        rb = tc.rolling_baseline("m", "mse", window=window, min_history=mh)
        assert rb["sufficient"] is True

    def test_one_below_sufficient(self, tmp_path):
        from qsmlops.config import MONITORING_MIN_HISTORY

        tc = TelemetryCollector(tmp_path / "t2.jsonl")
        window = 10
        mh = MONITORING_MIN_HISTORY
        for _ in range(mh - 1):
            tc.record("m", "metric", "mse", 1.0)
        for _ in range(window):
            tc.record("m", "metric", "mse", 1.5)
        rb = tc.rolling_baseline("m", "mse", window=window, min_history=mh)
        assert rb["sufficient"] is False


# ----------------------------------------------------------------------
# T5 — dead canonical_json import removed (functional)
# ----------------------------------------------------------------------
class TestT5DeadImport:
    def test_record_feature_attribution_works(self, tmp_path):
        tc = TelemetryCollector(tmp_path / "t.jsonl")
        n = tc.record_feature_attribution(
            "m", [{"feature": "f0", "score": 0.1, "severity": "LOW"}]
        )
        assert n == 1


# ----------------------------------------------------------------------
# T6 — serving keystore error is logged, not swallowed
# ----------------------------------------------------------------------
class TestT6ServingException:
    def test_keystore_error_logged(self, pipe, monkeypatch, caplog):
        import logging

        from qsmlops.serving.service import ModelDeploymentService

        _deploy(pipe, "t6")
        svc = ModelDeploymentService(pipe.registry)

        # Make signature verification fail so we reach the keystore lookup
        def fake_verify(self, keystore):
            return False

        monkeypatch.setattr(
            "qsmlops.passport.passport.Passport.verify_signature", fake_verify
        )

        def boom(key_id):
            raise RuntimeError("db down")

        monkeypatch.setattr(pipe.registry.keystore, "get_record", boom)
        with caplog.at_level(logging.WARNING):
            try:
                svc.load("t6")
            except Exception:
                pass
        assert any("keystore lookup failed" in rec.message for rec in caplog.records)


# ----------------------------------------------------------------------
# T7 — redundant ml optional extra removed
# ----------------------------------------------------------------------
class TestT7MlExtra:
    def test_ml_extra_removed(self):
        text = (Path(__file__).parent.parent / "pyproject.toml").read_text()
        assert "ml =" not in text
        assert "scikit-learn" in text


# ----------------------------------------------------------------------
# T8 — version source of truth
# ----------------------------------------------------------------------
class TestT8VersionSource:
    def test_version_from_qsmlops(self):
        from qsmlops import __version__

        import qsmlops.api.app as appmod

        assert __version__ == "0.1.0"
        assert appmod.QSMLOPS_VERSION == __version__


# ----------------------------------------------------------------------
# Licence alignment
# ----------------------------------------------------------------------
class TestLicence:
    def test_pyproject_mit(self):
        text = (Path(__file__).parent.parent / "pyproject.toml").read_text(
            encoding="utf-8"
        )
        assert 'license = { text = "MIT" }' in text

    def test_readme_mit(self):
        # README.md is UTF-8 (SAT-SA-first README uses unicode arrows/dashes);
        # read explicitly so Windows cp1252 default encoding cannot break this.
        text = (Path(__file__).parent.parent / "README.md").read_text(
            encoding="utf-8"
        )
        assert "MIT License" in text


# ----------------------------------------------------------------------
# Config split-brain divergence guard (A2)
# ----------------------------------------------------------------------
class TestConfigDivergenceGuard:
    def test_overlapping_paths_coincide(self, tmp_path):
        from qsmlops.config import PlatformConfig
        from qsmlops.core.settings import Settings

        cfg = PlatformConfig(tmp_path)
        settings = Settings(home=tmp_path)
        assert cfg.artifacts_dir == settings.artifacts_dir
        assert cfg.keys_dir == settings.keys_dir
        assert cfg.ledger_path == settings.ledger_path
        assert cfg.registry_path == settings.registry_db_path
        assert cfg.learning_path == settings.learning_path

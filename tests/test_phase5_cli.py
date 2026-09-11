"""Phase 5 CLI tests.

Drives the real click CLI (same commands operators use) through the trust
lifecycle: init -> provision -> train -> trust -> request-approval ->
registry -> revoke. CLI mutations must behave identically to API/service
calls because they share the same underlying code paths.
"""
from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from qsmlops.cli import cli


@pytest.fixture()
def home(tmp_path, monkeypatch):
    target = tmp_path / "cli_home"
    monkeypatch.setenv("QSMLOPS_HOME", str(target))
    runner = CliRunner()
    result = runner.invoke(
        cli, ["provision-dataset", "--name", "cli-data", "--samples", "120"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    return {"runner": runner, "path": target}


def _invoke(home, *args):
    result = home["runner"].invoke(cli, list(args), catch_exceptions=False)
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def _train(home, model="cli-model"):
    out = _invoke(home, "train", "--model", model, "--dataset", "cli-data")
    assert out["version"] == 1
    return out


class TestTrustCli:
    def test_trust_refresh_and_inspect(self, home):
        trained = _train(home)
        vid = trained["version_id"]

        refreshed = _invoke(home, "trust", "--version-id", vid, "--refresh")
        assert refreshed["decision"] == "TRUSTED"
        assert refreshed["promotion_eligible"] is True
        assert "components" in refreshed and "explanation" in refreshed

        latest = _invoke(home, "trust", "--version-id", vid)
        assert latest["report"]["decision"] == "TRUSTED"

    def test_trust_without_evaluation_fails_cleanly(self, home):
        trained = _train(home, model="unevaluated")
        runner = home["runner"]
        result = runner.invoke(
            cli, ["trust", "--version-id", trained["version_id"]], catch_exceptions=False
        )
        assert result.exit_code == 1
        assert "no trust evaluation" in result.output


class TestApprovalCli:
    def test_request_approval_promotes_verified_model(self, home):
        trained = _train(home)
        vid = trained["version_id"]
        _invoke(home, "verify", "--version-id", vid)

        approval = _invoke(
            home, "request-approval", "--version-id", vid, "--approver", "gov-bot"
        )
        assert approval["state"] == "APPROVED"
        assert approval["approver"] == "gov-bot"
        assert approval["trust_decision"] in ("TRUSTED", "CONDITIONALLY_TRUSTED")

    def test_request_approval_denied_is_structured(self, home):
        trained = _train(home, model="denied")
        vid = trained["version_id"]
        _invoke(home, "verify", "--version-id", vid)

        # corrupt the artifact at its content address: gate must refuse
        from qsmlops.config import PlatformConfig

        config = PlatformConfig()  # resolves QSMLOPS_HOME from the environment
        artifact_path = config.artifacts_dir / trained["artifact_digest"][:2] / trained["artifact_digest"]
        original = artifact_path.read_bytes()
        artifact_path.write_bytes(b"corrupted" + original)

        runner = home["runner"]
        result = runner.invoke(
            cli,
            ["request-approval", "--version-id", vid, "--approver", "op"],
            catch_exceptions=False,
        )
        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["approval"] == "DENIED"
        assert "refused" in payload["reason"].lower()

    def test_approve_and_deploy_command_reports_denial_structurally(self, home):
        trained = _train(home, model="legacy-denied")
        vid = trained["version_id"]
        _invoke(home, "verify", "--version-id", vid)

        from qsmlops.config import PlatformConfig

        config = PlatformConfig()
        artifact_path = config.artifacts_dir / trained["artifact_digest"][:2] / trained["artifact_digest"]
        artifact_path.write_bytes(b"x" + artifact_path.read_bytes())

        runner = home["runner"]
        result = runner.invoke(
            cli, ["approve-and-deploy", "--version-id", vid], catch_exceptions=False
        )
        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload.get("approval") == "DENIED" or payload.get("approved") is False

    def test_deprecated_approve_alias_warns_and_deploys(self, home):
        """C4: the deprecated `approve` alias still works (legacy behaviour)
        but emits a deprecation warning on stderr."""
        trained = _train(home, model="alias-deploy")
        vid = trained["version_id"]
        _invoke(home, "verify", "--version-id", vid)

        runner = home["runner"]
        result = runner.invoke(
            cli, ["approve", "--version-id", vid], catch_exceptions=False
        )
        # Warning is on stderr; the JSON result is on stdout (pretty-printed
        # across multiple lines). Reconstruct the JSON by dropping the
        # deprecation warning line.
        assert "deprecated" in result.output
        json_lines = [
            line for line in result.output.splitlines()
            if not line.strip().startswith("WARNING")
        ]
        payload = json.loads("\n".join(json_lines))
        assert payload.get("approved") is True
        # The alias performs a real deploy: the version reaches DEPLOYED.
        listing = _invoke(home, "registry")
        deployed = [v for v in listing["versions"] if v["version_id"] == vid]
        assert deployed and deployed[0]["state"] == "DEPLOYED"


class TestRegistryCli:
    def test_registry_listing_and_revocation(self, home):
        trained = _train(home)
        vid = trained["version_id"]
        _invoke(home, "verify", "--version-id", vid)
        _invoke(home, "request-approval", "--version-id", vid)

        listing = _invoke(home, "registry")
        row = next(r for r in listing["versions"] if r["version_id"] == vid)
        assert row["state"] == "APPROVED"
        assert row["trust_decision"] in ("TRUSTED", "CONDITIONALLY_TRUSTED")
        assert listing["ledger_chain_ok"] is True

        revoked = _invoke(
            home, "revoke", "--version-id", vid, "--reason", "incident", "--actor", "secops"
        )
        assert revoked["revoked"] is True

        listing = _invoke(home, "registry")
        row = next(r for r in listing["versions"] if r["version_id"] == vid)
        assert row["state"] == "REVOKED"


class TestDeployCli:
    def test_deploy_deploys_latest_approved_version(self, home):
        trained = _train(home)
        vid = trained["version_id"]
        _invoke(home, "verify", "--version-id", vid)
        _invoke(home, "request-approval", "--version-id", vid, "--approver", "gov-bot")

        out = _invoke(home, "deploy", "--model", "cli-model")
        assert out.get("deployment") != "DENIED"
        assert out["state"] == "DEPLOYED"
        assert "deployment_id" in out

    def test_deploy_without_approved_version_is_denied(self, home):
        trained = _train(home, model="not-approved")
        vid = trained["version_id"]
        _invoke(home, "verify", "--version-id", vid)

        runner = home["runner"]
        result = runner.invoke(
            cli, ["deploy", "--model", "not-approved"], catch_exceptions=False
        )
        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["deployment"] == "DENIED"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

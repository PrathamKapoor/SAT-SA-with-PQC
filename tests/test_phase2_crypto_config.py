"""Phase 2 — cryptographic suite configuration regression tests.

Reproduces and closes the Phase 1 finding (quantum-trust-audit.md QT-07 /
requirements-traceability.md GAP-10): AgilityEngine used to always
auto-select the strongest available suite (ML-DSA-87 + ML-KEM-1024),
silently ignoring configs/settings.*.yaml's declared
crypto.default_signature_algorithm / crypto.default_key_encryption_algorithm
(ML-DSA-65 + ML-KEM-768). ServiceContainer._platform_config() only forwarded
``settings.home`` into PlatformConfig, dropping the crypto section entirely.

These tests verify: (1) the legacy no-configuration path is unchanged
(backward compatibility), (2) an explicitly configured suite is what
actually gets selected, (3) invalid/inconsistent configuration fails closed
with an actionable error instead of silently substituting a suite, and
(4) the full settings -> container -> pipeline -> AgilityEngine path agrees
end to end for every declared environment profile.
"""
from __future__ import annotations

import pathlib
import tempfile

import pytest

from qsmlops.crypto.agility import AgilityEngine
from qsmlops.crypto.providers import ProviderError


def test_legacy_no_config_still_auto_selects_strongest():
    """Backward compatibility: every existing call site constructs
    AgilityEngine() with no arguments and expects the pre-Phase-2 behaviour."""
    ae = AgilityEngine()
    policy = ae.effective_policy()
    assert policy["configured"] is False
    assert policy["source"] == "auto-selected-strongest"
    assert policy["signature_algorithm"] == "ML-DSA-87"
    assert policy["kem_algorithm"] == "ML-KEM-1024"
    assert ae.default_suite == "QS-55-ML-DSA-87+ML-KEM-1024"


def test_configured_suite_is_authoritative():
    ae = AgilityEngine(
        default_signature_algorithm="ML-DSA-65",
        default_kem_algorithm="ML-KEM-768",
    )
    policy = ae.effective_policy()
    assert policy["configured"] is True
    assert policy["source"] == "configured"
    assert policy["signature_algorithm"] == "ML-DSA-65"
    assert policy["kem_algorithm"] == "ML-KEM-768"
    assert ae.default_suite == "QS-33-ML-DSA-65+ML-KEM-768"
    # select_suite() with no explicit suite_id must resolve to the same one.
    assert ae.select_suite().suite_id == ae.default_suite


def test_partial_configuration_fails_closed():
    """One of the pair set without the other is an inconsistent
    configuration; it must never silently fall back to auto-selection."""
    with pytest.raises(ProviderError, match="configured together"):
        AgilityEngine(default_signature_algorithm="ML-DSA-65")
    with pytest.raises(ProviderError, match="configured together"):
        AgilityEngine(default_kem_algorithm="ML-KEM-768")


def test_unknown_configured_algorithm_fails_closed():
    with pytest.raises(ProviderError, match="not a known provider"):
        AgilityEngine(
            default_signature_algorithm="ML-DSA-999",
            default_kem_algorithm="ML-KEM-768",
        )
    with pytest.raises(ProviderError, match="not a known provider"):
        AgilityEngine(
            default_signature_algorithm="ML-DSA-65",
            default_kem_algorithm="ML-KEM-9999",
        )


@pytest.mark.parametrize("env", ["development", "testing", "production"])
def test_settings_to_runtime_suite_agreement(env, tmp_path):
    """End-to-end regression for the exact gap Phase 1 found: the suite the
    running pipeline actually uses must equal the suite configs/settings.*.yaml
    declares, for every environment profile — not merely for one."""
    from qsmlops.core.context import ServiceContainer
    from qsmlops.core.settings import load_settings

    home = tmp_path / f"home_{env}"
    settings = load_settings(env=env, overrides={"home": home})
    container = ServiceContainer(settings)
    try:
        container.initialize()
        pipeline = container.get("pipeline")
        policy = pipeline.agility.effective_policy()
        assert policy["configured"] is True, (
            f"env={env}: declared crypto settings had no effect on the "
            f"running suite (regressed to auto-selection)"
        )
        assert policy["signature_algorithm"] == settings.crypto.default_signature_algorithm
        assert policy["kem_algorithm"] == settings.crypto.default_key_encryption_algorithm

        # The identity service must share the same engine instance as the
        # pipeline, not independently default to a different suite.
        identity_service = container.get("identity_service")
        assert identity_service._agility is pipeline.agility
    finally:
        container.close()


def test_security_api_route_exposes_effective_policy(tmp_path):
    """The /security route (Phase 2) must expose enough to audit which
    suite is actually active, without exposing key material."""
    from qsmlops.core.context import ServiceContainer
    from qsmlops.core.settings import load_settings
    from fastapi.testclient import TestClient
    from qsmlops.app import build_app

    settings = load_settings(env="testing", overrides={"home": tmp_path / "api_home"})
    container = ServiceContainer(settings)
    container.initialize()
    try:
        client = TestClient(build_app(container))
        resp = client.get("/security")
        assert resp.status_code == 200
        body = resp.json()
        assert "crypto_policy" in body
        assert body["crypto_policy"]["configured"] is True
        assert body["crypto_policy"]["signature_algorithm"] == "ML-DSA-65"
        # never leak secret key material through this diagnostic surface
        dumped = str(body)
        assert "private_key" not in dumped.lower()
        assert "passphrase" not in dumped.lower()
    finally:
        container.close()

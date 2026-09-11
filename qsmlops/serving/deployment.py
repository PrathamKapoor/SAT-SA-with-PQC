"""Governed deployment service (Phase 6).

Implements the deployment-request boundary required by the Secure Model
Deployment phase:

    Request -> Identity -> Registry state -> Cryptographic gates
            -> Trust eligibility (Phase 5) -> Environment validation
            -> Policy -> registry.deploy() -> Post-deployment verification

The registry remains the SOLE promotion mechanism: this service requests and
authorises, it never mutates model state directly. Every terminal outcome is
audited in the evidence ledger. Failures raise :class:`DeploymentError`
carrying structured, explainable details.
"""
from __future__ import annotations

import time

from qsmlops.registry.registry import ModelRegistry
from qsmlops.serving.environment import validate_environment
from qsmlops.serving.service import ModelDeploymentService
from qsmlops.supervisor.policy import build_facts, default_policy_engine

DEPLOYABLE_STATES = {"APPROVED", "DEPLOYED"}  # DEPLOYED => re-deploy/restore


class DeploymentError(Exception):
    """Structured deployment failure; `.details` explains every refusal."""

    def __init__(self, reason: str, details: dict | None = None) -> None:
        super().__init__(reason)
        self.details = {"reason": reason, **(details or {})}

    def to_dict(self) -> dict:
        return dict(self.details)


class DeploymentService:
    def __init__(self, registry: ModelRegistry, policy_engine=None) -> None:
        self.registry = registry
        self.policy_engine = policy_engine or default_policy_engine()

    # ------------------------------------------------------------------
    def ledger_append(self, record: dict) -> None:
        self.registry.ledger.append(record)

    def _deny(self, version_id: str, actor: str, reason: str, **details) -> "DeploymentError":
        payload = {"version_id": version_id, "actor": actor,
                   "target_environment": details.pop("target_environment", ""),
                   "reason": reason, "at": time.time(), **details}
        self.ledger_append({"type": "deployment_denied", **payload})
        return DeploymentError(reason, payload)

    def _resolve_version(self, version_id: str | None, model_name: str | None) -> str:
        if version_id:
            return version_id
        if not model_name:
            raise ValueError("deployment request requires model_name or version_id")
        approved = [
            v for v in self.registry.list_versions(model_name)
            if v["state"] == "APPROVED"
        ]
        if not approved:
            raise KeyError(f"no APPROVED version available for {model_name!r}")
        return approved[-1]["version_id"]

    def _signer_owner(self, passport) -> str:
        if passport is None or passport.signature is None:
            return ""
        return passport.signature.signer_key_id.split("-")[0]

    # ------------------------------------------------------------------
    def validate(
        self,
        version_id: str,
        actor: str,
        target_environment: str = "production",
    ) -> dict:
        """Run every pre-deployment gate WITHOUT promoting. Fully auditable."""
        checks: list[dict] = []

        def check(name: str, passed: bool, detail: str = "") -> bool:
            checks.append({"name": name, "passed": bool(passed), "detail": detail})
            return bool(passed)

        rec = self.registry.get_version(version_id)  # KeyError if unknown
        passport = self.registry.load_passport(version_id)

        # 1. identity / authorization -----------------------------------
        check("actor_identified", bool(actor and actor.strip()),
              "requesting actor must be a non-empty identity")
        signer_owner = self._signer_owner(passport)
        separation_ok = check(
            "separation_of_duties",
            bool(signer_owner) and actor != signer_owner,
            f"deploying actor must differ from signer owner ({signer_owner or 'unknown'})",
        )

        # 2. registry state ----------------------------------------------
        state = rec["state"]
        state_ok = check("registry_state_deployable", state in DEPLOYABLE_STATES,
                         f"state={state}; deployable states: {sorted(DEPLOYABLE_STATES)}")

        # 3. cryptographic gates -----------------------------------------
        signature_valid = False
        try:
            signature_valid = bool(passport.verify_signature(self.registry.keystore))
        except Exception:
            signature_valid = False
        check("passport_signature_valid", signature_valid)
        artifact_intact = self.registry.artifacts.verify(rec["artifact_digest"])
        check("artifact_integrity", artifact_intact)
        signer_status = "unknown"
        try:
            key_rec = self.registry.keystore.get_record(passport.signature.signer_key_id)
            signer_status = key_rec.status
            expired = getattr(key_rec, "is_expired", lambda: False)()
            check("signer_key_usable", signer_status == "active" and not expired,
                  f"status={signer_status}")
        except (KeyError, AttributeError):
            # S5: a malformed signer/key interface (missing record attribute)
            # must fail closed the same way an absent key does — never an
            # unexpected crash or accidental acceptance.
            check("signer_key_usable", False, "signer key absent or malformed in trust anchors")

        # 4. trust eligibility — recomputed FRESH at deploy time. We never reuse
        #    a cached `latest_trust` decision here: a trust evaluation captured
        #    earlier could be invalidated by subsequent key rotation, revocation
        #    or state changes, so the deployment gate must re-derive eligibility
        #    against *current* evidence. This re-evaluation is not persisted; it
        #    only gates this deployment.
        trust_result = self.registry.trust_evaluation(
            version_id, actor="deployment-validate", persist=False)
        trust_summary = trust_result.to_dict()
        decision = trust_summary.get("decision", "")
        eligible = bool(trust_summary.get("promotion_eligible")) and decision in (
            "TRUSTED", "CONDITIONALLY_TRUSTED",
        )
        check("trust_promotion_eligible", eligible,
              f"decision={decision or 'NONE'}; blockers="
              f"{trust_summary.get('blocking_conditions', [])}")

        # 5. environment validation --------------------------------------
        bom = None
        load_bom = getattr(self.registry, "_load_bom_lenient", None)
        if load_bom is not None:
            bom = load_bom(rec["bom_digest"])
        env_report = validate_environment(passport, bom, target_environment)
        check("environment_compatible", env_report.compatible,
              "; ".join(
                  f"{c.name}:{c.status}" for c in env_report.checks if c.status != "OK"
              ) or "all declared requirements verified")

        # 6. policy --------------------------------------------------------
        facts = build_facts(
            [], risk_score=0.0, per_agent_risk={},
            version_record=rec,
            scores={"security_score": trust_summary.get("security_score")},
            trust={
                "trust_score": trust_summary.get("trust_score"),
                "decision": decision,
                "promotion_eligible": eligible,
                "blocking_conditions": trust_summary.get("blocking_conditions", []),
            },
        )
        facts["signature_invalid"] = not signature_valid
        policy_block = self.policy_engine.deployment_blocked(facts)
        check("policy_allows_deployment", policy_block is None,
              policy_block.rule_name if policy_block else "no blocking rule fired")

        compatible = all(c["passed"] for c in checks)
        report = {
            "version_id": version_id,
            "model_name": rec["model_name"],
            "state": state,
            "actor": actor,
            "target_environment": target_environment,
            "eligible": compatible,
            "checks": checks,
            "environment": env_report.to_dict(),
            "trust_decision": decision,
            "trust_score": trust_summary.get("trust_score"),
            "validated_at": time.time(),
        }
        self.ledger_append({
            "type": "deployment_validation",
            "version_id": version_id,
            "actor": actor,
            "target_environment": target_environment,
            "eligible": compatible,
            "failed_checks": [c["name"] for c in checks if not c["passed"]],
        })
        return report

    # ------------------------------------------------------------------
    def request(
        self,
        model_name: str | None = None,
        version_id: str | None = None,
        actor: str = "",
        target_environment: str = "production",
    ) -> dict:
        """Validate then promote through registry.deploy (sole mechanism)."""
        self.ledger_append({
            "type": "deployment_requested",
            "model": model_name or "",
            "version_id": version_id or "",
            "actor": actor,
            "target_environment": target_environment,
            "at": time.time(),
        })
        try:
            resolved_vid = self._resolve_version(version_id, model_name)
        except KeyError as exc:
            err = self._deny(version_id or model_name or "", actor,
                             str(exc), target_environment=target_environment)
            raise err

        try:
            validation = self.validate(resolved_vid, actor, target_environment)
        except KeyError as exc:
            err = self._deny(resolved_vid, actor,
                             f"unknown version: {exc}",
                             target_environment=target_environment)
            raise err
        if not validation["eligible"]:
            failed = [c["name"] for c in validation["checks"] if not c["passed"]]
            err = self._deny(
                resolved_vid, actor,
                f"deployment validation failed: {', '.join(failed)}",
                target_environment=target_environment,
                failed_checks=failed,
                environment=validation["environment"],
                trust_decision=validation["trust_decision"],
            )
            raise err

        # SOLE promotion mechanism — the registry performs the transition.
        deployment_id = self.registry.deploy(resolved_vid, actor)

        # Post-deployment verification via the existing serving gates.
        verification = {"passed": True, "detail": ""}
        try:
            service = ModelDeploymentService(self.registry)
            service.load(validation["model_name"])
            active = self.registry.active_deployment(validation["model_name"])
            if not active or active["version_id"] != resolved_vid:
                verification = {"passed": False,
                                "detail": "active deployment does not match requested version"}
        except Exception as exc:  # serving refused the promoted model
            verification = {"passed": False, "detail": f"{type(exc).__name__}: {exc}"}

        result = {
            "deployment_id": deployment_id,
            "version_id": resolved_vid,
            "model_name": validation["model_name"],
            "state": "DEPLOYED",
            "actor": actor,
            "target_environment": target_environment,
            "validation": validation,
            "post_verification": verification,
            "serving_healthy": bool(verification["passed"]),
            "completed_at": time.time(),
        }
        if verification["passed"]:
            self.ledger_append({
                "type": "deployment_completed",
                "version_id": resolved_vid,
                "deployment_id": deployment_id,
                "actor": actor,
                "target_environment": target_environment,
            })
        else:
            self.ledger_append({
                "type": "deployment_failed_postverification",
                "version_id": resolved_vid,
                "deployment_id": deployment_id,
                "actor": actor,
                "detail": verification["detail"],
            })
            err = DeploymentError(
                "promoted but post-deployment verification failed; "
                "rollback recommended",
                result,
            )
            raise err
        return result

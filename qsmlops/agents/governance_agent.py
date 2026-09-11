"""Governance Agent (Phase 9).

Consumes existing governance evidence — passport signature vs trust anchors,
QML-BOM entry verifiability, declared security metadata, registry state, and
the persisted Phase-5 trust decision — and emits compliance findings. It
creates no new trust/registry/policy authority; it interprets the existing
one.
"""
from __future__ import annotations

from qsmlops.agents.base import BaseAgent, Evidence, Observation, make_finding


class GovernanceAgent(BaseAgent):
    name = "governance-agent"

    def __init__(self, registry) -> None:
        self.registry = registry

    def observe(self, context: dict) -> Observation:
        findings = []
        subject = context.get("subject_id", "")
        passport = context.get("passport")
        keystore = context.get("keystore") or self.registry.keystore
        version_record = context.get("version_record") or {}

        # 1. cryptographic identity compliance ----------------------------
        signed = passport is not None and passport.signature is not None
        sig_ok = False
        if signed:
            try:
                sig_ok = bool(passport.verify_signature(keystore))
            except Exception:
                sig_ok = False
        findings.append(make_finding(
            "governance_signature_valid", sig_ok,
            "CRITICAL", "" if sig_ok else "passport signature not verifiable",
            observation=("passport signature verifies against trust anchors"
                         if sig_ok else "passport signature failed verification"),
            evidence=[Evidence("trust_anchors", "crypto",
                               {"signed": signed, "signature_valid": sig_ok,
                                "signer": getattr(getattr(passport, "signature", None),
                                                  "signer_key_id", "")})],
            confidence=1.0,
            recommendation="" if sig_ok else "QUARANTINE",
        ))

        # 2. supply-chain declaration completeness ------------------------
        bom = context.get("bom")
        entries = list(getattr(bom, "entries", []) or []) if bom is not None else []
        verified = sum(1 for e in entries if self.registry.artifacts.verify(e.digest))
        complete = bool(entries) and verified == len(entries)
        findings.append(make_finding(
            "governance_bom_declared_and_verified", complete,
            "HIGH" if not complete else "LOW",
            f"{verified}/{len(entries)} BOM entries verified in artifact store",
            observation=(f"QML-BOM: {verified}/{len(entries)} entries re-verified"
                         if entries else "no QML-BOM entries declared"),
            evidence=[Evidence("artifact_store", "crypto",
                               {"declared": len(entries), "verified": verified})],
            confidence=1.0,
            recommendation="" if complete else "REVIEW_SUPPLY_CHAIN",
        ))

        # 3. security metadata declared on the passport --------------------
        sec = (getattr(passport, "security_status", {}) or {}) if passport else {}
        missing_sec = [k for k in ("hash_algorithm", "suite_id",
                                   "signature_algorithm") if not sec.get(k)]
        findings.append(make_finding(
            "governance_security_metadata_declared", not missing_sec,
            "MEDIUM",
            f"security_status missing {', '.join(missing_sec)}" if missing_sec
            else f"suite {sec.get('suite_id')} declared",
            observation=("security metadata fully declared"
                         if not missing_sec else
                         f"security metadata incomplete ({', '.join(missing_sec)})"),
            evidence=[Evidence("passport.security_status", "log",
                               {"missing": missing_sec})],
            confidence=0.95,
        ))

        # 4. lifecycle-state compliance -----------------------------------
        legal_states = {"REGISTERED", "VERIFIED", "APPROVED", "DEPLOYED",
                        "QUARANTINED", "ROLLED_BACK", "REVOKED"}
        state = version_record.get("state", "")
        findings.append(make_finding(
            "governance_state_legal", state in legal_states,
            "CRITICAL", f"registry state={state}",
            observation=f"version resides in governed state {state}",
            evidence=[Evidence("model_registry", "log", {"state": state})],
            confidence=1.0,
        ))

        # 5. Phase-5 trust evaluation exists -------------------------------
        latest = self.registry.latest_trust(subject) if hasattr(self.registry, "latest_trust") else None
        pending_states = {"REGISTERED"}   # trust evaluation happens at verification
        awaiting_evaluation = state in pending_states
        required = state in {"APPROVED", "DEPLOYED"}
        passed = (latest is not None) or awaiting_evaluation or not required
        severity = "MEDIUM" if (not passed and required) else (
            "LOW" if awaiting_evaluation else "LOW")
        findings.append(make_finding(
            "governance_trust_evaluation_present", passed,
            severity,
            "" if latest else ("trust evaluation pending (state "
                               f"{state or 'unknown'})") ,
            observation=("persisted trust decision available: "
                         f"{latest['trust_decision']}" if latest else
                         f"trust evaluation pending for state {state or 'unknown'}"),
            evidence=[Evidence("registry.trust", "log",
                               {"present": latest is not None,
                                "state": state})],
            confidence=1.0,
            recommendation="EVALUATE_TRUST" if latest is None else "",
        ))

        failed = [f for f in findings if not f.passed]
        rec = "ACCEPT"
        if any(not f.passed and f.severity == "CRITICAL" for f in failed):
            rec = "BLOCK"
        elif failed:
            rec = "REVIEW"
        return Observation(agent=self.name, subject_id=subject,
                           recommendation=rec, findings=findings,
                           notes=f"governance sweep over {len(findings)} checks")

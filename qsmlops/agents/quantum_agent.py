"""Quantum Security Agent: cryptographic posture verification.

Checks passport signatures against trust anchors, suite status (deprecated
algorithms refused), and signing-key freshness against the rotation policy.
"""
from __future__ import annotations

import time

from qsmlops.agents.base import BaseAgent, Evidence, Finding, Observation, make_finding
from qsmlops.crypto.agility import (
    AgilityEngine,
    STATUS_DEPRECATED,
    STATUS_EMERGENCY,
)
from qsmlops.config import DEFAULT_KEY_MAX_AGE_DAYS
from qsmlops.passport.passport import Passport


class QuantumSecurityAgent(BaseAgent):
    name = "quantum-security-agent"

    def __init__(
        self, agility: AgilityEngine, key_max_age_days: float = DEFAULT_KEY_MAX_AGE_DAYS
    ) -> None:
        self.agility = agility
        self.key_max_age_days = key_max_age_days

    def observe(self, context: dict) -> Observation:
        passport: Passport | None = context.get("passport")
        keystore = context.get("keystore")
        findings: list[Finding] = []
        if passport is None or passport.signature is None:
            findings.append(
                make_finding(
                    "passport_signed", False, "CRITICAL", "passport missing or unsigned",
                    observation="model has no ML-DSA signature block; origin cannot be proven",
                    evidence=[Evidence(
                        "passport_document", "crypto",
                        {"signature_present": False,
                         "passport_id": getattr(passport, "passport_id", "")},
                    )],
                    confidence=1.0,
                    recommendation="QUARANTINE",
                )
            )
            return Observation(
                agent=self.name,
                subject_id=context.get("subject_id", ""),
                recommendation="QUARANTINE",
                findings=findings,
            )
        sig_ok = passport.verify_signature(keystore)
        findings.append(
            make_finding(
                "passport_signature_valid",
                sig_ok,
                "CRITICAL",
                f"signed by {passport.signature.signer_key_id}",
                observation=(
                    f"ML-DSA signature over passport digest verified against trust anchor "
                    f"{passport.signature.signer_key_id}"
                    if sig_ok
                    else f"signature verification FAILED for signer {passport.signature.signer_key_id}"
                ),
                evidence=[Evidence(
                    "ml_dsa_verifier", "crypto",
                    {
                        "suite_id": passport.signature.suite_id,
                        "algorithm": passport.signature.algorithm_id,
                        "signer_key_id": passport.signature.signer_key_id,
                        "signed_digest": passport.signature.signed_digest,
                        "recomputed_digest": passport.digest(),
                        "signed_at": passport.signature.signed_at,
                    },
                    description="ML-DSA verification against KeyStore trust anchor",
                )],
                confidence=1.0 if not sig_ok else 0.999,
                recommendation="QUARANTINE" if not sig_ok else "",
            )
        )
        try:
            suite = self.agility.get_suite(passport.signature.suite_id)
            deprecated = suite.status == STATUS_DEPRECATED
            emergency = suite.status == STATUS_EMERGENCY
            findings.append(
                make_finding(
                    "suite_current",
                    not deprecated,
                    "HIGH" if not emergency else "MEDIUM",
                    f"suite {suite.suite_id} status={suite.status}",
                    observation=(
                        f"cipher suite {suite.suite_id} is {suite.status}"
                        + (" (usable only under break-glass)" if emergency else "")
                    ),
                    evidence=[Evidence(
                        "agility_engine", "external",
                        {"suite_id": suite.suite_id, "status": suite.status,
                         "signature_algorithm": suite.signature_algorithm,
                         "kem_algorithm": suite.kem_algorithm},
                    )],
                    confidence=0.95,
                    recommendation="ROTATE_KEYS" if deprecated else "",
                )
            )
        except Exception:
            findings.append(
                make_finding(
                    "suite_known", False, "CRITICAL",
                    f"unknown suite {passport.signature.suite_id!r}",
                    observation=f"passport declares unknown cipher suite {passport.signature.suite_id!r}",
                    evidence=[Evidence(
                        "agility_engine", "external",
                        {"declared_suite": passport.signature.suite_id},
                    )],
                    confidence=0.99,
                    recommendation="QUARANTINE",
                )
            )
        try:
            signer_record = keystore.get_record(passport.signature.signer_key_id)
            age_days = (time.time() - signer_record.created_at) / 86400
            fresh = age_days <= self.key_max_age_days
            expired = signer_record.is_expired()
            findings.append(
                make_finding(
                    "signing_key_within_rotation_window",
                    fresh and not expired,
                    "MEDIUM",
                    f"key age {age_days:.1f}d / limit {self.key_max_age_days:.0f}d"
                    + ("; KEY EXPIRED" if expired else ""),
                    observation=(
                        f"signing key age {age_days:.1f}d vs rotation policy "
                        f"{self.key_max_age_days:.0f}d" + (" — key EXPIRED" if expired else "")
                    ),
                    evidence=[Evidence(
                        "keystore", "crypto",
                        {
                            "key_id": signer_record.key_id,
                            "created_at": signer_record.created_at,
                            "expires_at": signer_record.expires_at,
                            "age_days": round(age_days, 2),
                            "max_age_days": self.key_max_age_days,
                            "status": signer_record.status,
                        },
                        description="signing-key freshness against rotation policy",
                    )],
                    confidence=0.9,
                    recommendation="ROTATE_KEYS" if (not fresh or expired) else "",
                )
            )
        except Exception:
            findings.append(
                make_finding(
                    "signer_registered", False, "CRITICAL", "signer not in trust store",
                    observation=f"signer key {passport.signature.signer_key_id} absent from trust anchors",
                    evidence=[Evidence(
                        "keystore", "crypto",
                        {"requested_key_id": passport.signature.signer_key_id},
                    )],
                    confidence=0.99,
                    recommendation="QUARANTINE",
                )
            )
        rec = "ACCEPT"
        if any(not f.passed and f.severity == "CRITICAL" for f in findings):
            rec = "QUARANTINE"
        elif any(not f.passed for f in findings):
            rec = "ROTATE_KEYS"
        return Observation(
            agent=self.name,
            subject_id=context.get("subject_id", ""),
            recommendation=rec,
            findings=findings,
        )

"""Trust and security scoring.

Single source of truth for the numeric scores surfaced by the dashboard API
and consumed by the policy engine as facts:

- security_score : cryptographic posture (signature validity, key freshness,
  suite status, artifact integrity). 100 = fully sound.
- trust_score    : overall confidence in a model version (crypto posture +
  agent findings + drift status). 100 = no open concerns.

Phase 5 extends this module (without changing the two functions above) with
the explainable trust evaluation required by the Secure Model Registry:
`evaluate_trust` derives a composite score from actual evidence — signature
verification, artifact integrity, BOM verifiability, provenance completeness,
metric thresholds and agent observations — and maps it onto an explicit trust
decision. Hard cryptographic failures always dominate: they produce BLOCKED
regardless of any numeric score.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from qsmlops.agents.base import Finding, Observation
from qsmlops.config import DEFAULT_METRIC_THRESHOLDS, DEFAULT_TRUST_THRESHOLDS

SEVERITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

_SEVERITY_DEDUCTION = {"LOW": 2.0, "MEDIUM": 8.0, "HIGH": 20.0, "CRITICAL": 45.0}

# Component weights for the composite trust score. Components with no
# available evidence are excluded and the remaining weights renormalised.
_COMPONENT_WEIGHTS: dict[str, float] = {
    "security": 0.35,
    "integrity": 0.25,
    "lineage": 0.15,
    "performance": 0.15,
    "operational": 0.10,
}

# Provenance fields that constitute complete dataset lineage (Phase 4
# passports record these; older/partial passports score proportionally).
_LINEAGE_PROVENANCE_FIELDS = (
    "bom_digest",
    "dataset_name",
    "dataset_digest",
    "n_samples",
    "feature_names",
)

# (BOM kind, points) pairs rewarding declared supply-chain coverage.
_LINEAGE_BOM_KINDS = (("dataset", 15), ("code", 10), ("framework", 10), ("hardware", 5))

_DRIFT_SEVERITY_PENALTY = {"CRITICAL": 60.0, "HIGH": 30.0, "MEDIUM": 15.0}


def _deduction(findings: list[Finding]) -> float:
    total = 0.0
    for f in findings:
        if f.passed:
            continue
        # low-confidence findings deduct less; high-confidence more
        weight = 0.5 + 0.5 * max(0.0, min(1.0, f.confidence))
        total += _SEVERITY_DEDUCTION.get(f.severity, 5.0) * weight
    return min(100.0, total)


def compute_security_score(
    observations: list[Observation],
    passport=None,
    keystore=None,
) -> float:
    """Cryptographic posture in [0, 100]."""
    crypto_findings: list[Finding] = []
    for obs in observations:
        if obs.agent in ("quantum-security-agent", "security-agent", "red-team-agent", "data-agent"):
            crypto_findings.extend(obs.findings)
    score = 100.0 - _deduction(crypto_findings)
    if passport is not None and passport.signature is not None and keystore is not None:
        try:
            rec = keystore.get_record(passport.signature.signer_key_id)
            age_days = (time.time() - rec.created_at) / 86400
            if age_days > 365:
                score -= 5.0
            if getattr(rec, "expires_at", None) and rec.is_expired():
                score -= 25.0
        except Exception:
            score -= 30.0
    return round(max(0.0, min(100.0, score)), 2)


def compute_trust_score(
    observations: list[Observation],
    security_score: float | None = None,
    drift_summary: dict | None = None,
) -> float:
    """Overall model trust in [0, 100]."""
    all_findings = [f for obs in observations for f in obs.findings]
    score = 100.0 - _deduction(all_findings)
    if security_score is not None:
        # trust cannot exceed cryptographic posture by much
        score = min(score, security_score + 10.0)
    if drift_summary:
        sev = str(drift_summary.get("max_severity", "NONE")).upper()
        if sev == "CRITICAL":
            score -= 35.0
        elif sev == "HIGH":
            score -= 20.0
        elif sev == "MEDIUM":
            score -= 8.0
    return round(max(0.0, min(100.0, score)), 2)


def compute_scores(observations, passport=None, keystore=None, drift_summary=None):
    sec = compute_security_score(observations, passport, keystore)
    trust = compute_trust_score(observations, sec, drift_summary)
    return {
        "security_score": sec,
        "trust_score": trust,
    }


# ----------------------------------------------------------------------
# Phase 5: explainable trust evaluation
# ----------------------------------------------------------------------

@dataclass
class TrustResult:
    """Explainable outcome of a trust evaluation.

    Every field is derived from supplied evidence; the factor lists record
    the contributions so an auditor can reconstruct the score without
    re-running the evaluation.
    """

    version_id: str
    decision: str  # TRUSTED | CONDITIONALLY_TRUSTED | REVIEW_REQUIRED | BLOCKED | QUARANTINED
    trust_score: float
    security_score: float
    components: dict[str, float]
    positive_factors: list[dict] = field(default_factory=list)
    negative_factors: list[dict] = field(default_factory=list)
    blocking_conditions: list[str] = field(default_factory=list)
    promotion_eligible: bool = False
    evidence: dict = field(default_factory=dict)
    explanation: str = ""
    evaluated_at: float = field(default_factory=time.time)
    evaluated_by: str = "registry"

    def to_dict(self) -> dict:
        return {
            "version_id": self.version_id,
            "decision": self.decision,
            "trust_score": self.trust_score,
            "security_score": self.security_score,
            "components": self.components,
            "positive_factors": self.positive_factors,
            "negative_factors": self.negative_factors,
            "blocking_conditions": self.blocking_conditions,
            "promotion_eligible": self.promotion_eligible,
            "evidence": self.evidence,
            "explanation": self.explanation,
            "evaluated_at": self.evaluated_at,
            "evaluated_by": self.evaluated_by,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TrustResult":
        return cls(
            version_id=d["version_id"],
            decision=d["decision"],
            trust_score=float(d.get("trust_score", 0.0)),
            security_score=float(d.get("security_score", 0.0)),
            components=dict(d.get("components", {})),
            positive_factors=list(d.get("positive_factors", [])),
            negative_factors=list(d.get("negative_factors", [])),
            blocking_conditions=list(d.get("blocking_conditions", [])),
            promotion_eligible=bool(d.get("promotion_eligible", False)),
            evidence=dict(d.get("evidence", {})),
            explanation=d.get("explanation", ""),
            evaluated_at=float(d.get("evaluated_at", 0.0)),
            evaluated_by=d.get("evaluated_by", "registry"),
        )


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def evaluate_trust(
    version_id: str,
    version_record: dict | None = None,
    passport=None,
    keystore=None,
    artifact_store=None,
    bom=None,
    observations: list[Observation] | None = None,
    drift_summary: dict | None = None,
    thresholds: dict | None = None,
    evidence_extras: dict | None = None,
) -> TrustResult:
    """Derive an explainable trust result from actual evidence.

    Hard blockers (any one forces BLOCKED regardless of the composite):
      - passport missing or unsigned
      - passport signature fails verification against trust anchors
      - signer key revoked or unknown
      - artifact corrupted/missing in the content-addressed store
      - stored artifact digest differs from the passport claim

    All other weaknesses are scored deductions. The evaluation is
    deterministic: identical evidence yields an identical score.
    """
    observations = observations or []
    thresholds = {**DEFAULT_TRUST_THRESHOLDS, **(thresholds or {})}
    version_record = version_record or {}
    components: dict[str, float] = {}
    positive: list[dict] = []
    negative: list[dict] = []
    blocking: list[str] = []

    artifact_digest = version_record.get("artifact_digest", "")

    # ---------------- cryptographic identity ----------------
    if passport is None or passport.signature is None:
        blocking.append("passport_unsigned_or_missing")
        signature_valid = False
        signer_status = "unknown"
    else:
        try:
            signature_valid = bool(passport.verify_signature(keystore)) if keystore else False
        except Exception:
            # A signature/key error must fail CLOSED (block), never propagate
            # into an unhandled exception that would mask a hard crypto failure.
            signature_valid = False
            blocking.append("passport_signature_invalid")
        if not signature_valid:
            blocking.append("passport_signature_invalid")
        try:
            rec = keystore.get_record(passport.signature.signer_key_id)
            signer_status = rec.status
            if rec.status == "revoked":
                blocking.append("signer_key_revoked")
        except (KeyError, AttributeError):
            signer_status = "unknown"
            if signature_valid:
                blocking.append("signer_key_unknown")

    # ---------------- artifact integrity ----------------
    artifact_intact = bool(artifact_store.verify(artifact_digest)) if artifact_store and artifact_digest else False
    claimed_digest = (passport.identity.get("artifact_digest") if passport is not None else None)
    artifact_matches = bool(claimed_digest) and claimed_digest == artifact_digest
    if artifact_store is not None and artifact_digest and not artifact_intact:
        blocking.append("artifact_corrupted_or_missing")
    if passport is not None and not artifact_matches:
        blocking.append("artifact_passport_mismatch")

    # ---------------- component: security ----------------
    crypto_blockers = [b for b in blocking if b.startswith(("passport_", "signer_"))]
    security = 0.0 if crypto_blockers else compute_security_score(observations, passport, keystore)
    components["security"] = _clamp(security)

    # ---------------- component: integrity ----------------
    unverified_entries: list[str] = []
    verified_entry_count = 0
    if bom is not None:
        for entry in getattr(bom, "entries", []):
            if artifact_store is not None and artifact_store.verify(entry.digest):
                verified_entry_count += 1
            else:
                unverified_entries.append(f"{entry.kind}:{entry.name}")
    integrity = 100.0
    if bom is None:
        integrity -= 40.0
    integrity -= 25.0 * len(unverified_entries)
    if "artifact_corrupted_or_missing" in blocking or "artifact_passport_mismatch" in blocking:
        integrity = 0.0
    components["integrity"] = _clamp(integrity)
    if unverified_entries:
        negative.append({
            "component": "integrity",
            "detail": f"{len(unverified_entries)} BOM entr(y/ies) missing/corrupted: "
                      f"{', '.join(unverified_entries[:3])}",
        })
    else:
        positive.append({
            "component": "integrity",
            "detail": f"all {verified_entry_count} declared BOM entries re-verify in the artifact store",
        })

    # ---------------- component: lineage ----------------
    provenance = (passport.dataset_provenance if passport is not None else {}) or {}
    present_fields = [f for f in _LINEAGE_PROVENANCE_FIELDS if provenance.get(f)]
    missing_fields = [f for f in _LINEAGE_PROVENANCE_FIELDS if not provenance.get(f)]
    lineage = 12.0 * len(present_fields)
    bom_kinds_present = set()
    if bom is not None:
        bom_kinds_present = {e.kind for e in getattr(bom, "entries", [])}
        for kind, pts in _LINEAGE_BOM_KINDS:
            if kind in bom_kinds_present:
                lineage += pts
    components["lineage"] = _clamp(lineage)
    if missing_fields:
        negative.append({
            "component": "lineage",
            "detail": f"incomplete dataset provenance: missing {', '.join(missing_fields)}",
        })
    else:
        positive.append({"component": "lineage", "detail": "dataset provenance complete"})

    # ---------------- component: performance ----------------
    metrics = (passport.metrics if passport is not None else None) or {}
    r2, mse = metrics.get("r2"), metrics.get("mse")
    performance: float | None = None
    if r2 is not None and mse is not None:
        r2_ok = r2 >= DEFAULT_METRIC_THRESHOLDS["min_r2"]
        mse_ok = mse <= DEFAULT_METRIC_THRESHOLDS["max_mse"]
        performance = 100.0 if (r2_ok and mse_ok) else (50.0 if (r2_ok or mse_ok) else 0.0)
        components["performance"] = _clamp(performance)
        if r2_ok and mse_ok:
            positive.append({"component": "performance",
                             "detail": f"metrics within thresholds (r2={r2}, mse={mse})"})
        else:
            negative.append({"component": "performance",
                             "detail": f"metrics outside thresholds (r2={r2}, mse={mse})"})
    # metrics absent -> component excluded (no fabricated evidence)

    # ---------------- component: operational ----------------
    operational = 100.0
    if drift_summary:
        sev = str(drift_summary.get("max_severity", "NONE")).upper()
        penalty = _DRIFT_SEVERITY_PENALTY.get(sev, 0.0)
        operational -= penalty
        if penalty:
            negative.append({"component": "operational",
                             "detail": f"drift severity {sev} observed"})
    failed_findings = [
        (obs.agent, f) for obs in observations for f in obs.findings if not f.passed
    ]
    if failed_findings:
        operational -= min(40.0, 10.0 * len(failed_findings))
    components["operational"] = _clamp(operational)
    for agent, f in failed_findings:
        negative.append({
            "component": "operational",
            "detail": f"{agent}:{f.name} failed ({f.severity})",
        })

    # ---------------- composite ----------------
    weights_total = sum(
        w for name, w in _COMPONENT_WEIGHTS.items() if name in components
    )
    composite = (
        sum(components[name] * w for name, w in _COMPONENT_WEIGHTS.items() if name in components)
        / weights_total
        if weights_total
        else 0.0
    )
    composite = _clamp(composite)

    # ---------------- decision ----------------
    state = str(version_record.get("state", "")).upper()
    high_failures = [
        f for _, f in failed_findings
        if SEVERITY_ORDER.get(f.severity, 0) >= SEVERITY_ORDER["HIGH"]
    ]
    if state == "QUARANTINED":
        decision = "QUARANTINED"
    elif blocking:
        decision = "BLOCKED"
    elif composite >= thresholds["trusted"] and not high_failures:
        decision = "TRUSTED"
    elif composite >= thresholds["conditional"]:
        decision = "CONDITIONALLY_TRUSTED"
    else:
        decision = "REVIEW_REQUIRED"

    eligible = decision in ("TRUSTED", "CONDITIONALLY_TRUSTED")

    top_negative = "; ".join(n["detail"] for n in negative[:3]) if negative else "no open concerns"
    explanation = (
        f"{decision} ({composite}): components "
        f"{', '.join(f'{k}={v}' for k, v in components.items())}. "
        + (f"Blocking: {', '.join(blocking)}. " if blocking else "")
        + f"Factors: {top_negative}."
    )

    evidence = {
        "artifact_digest": artifact_digest,
        "signature_valid": signature_valid,
        "signer_status": signer_status,
        "bom_declared_entries": len(getattr(bom, "entries", []) or []) if bom is not None else 0,
        "bom_verified_entries": verified_entry_count,
        "observation_agents": sorted({o.agent for o in observations}),
        **(evidence_extras or {}),
    }

    return TrustResult(
        version_id=version_id,
        decision=decision,
        trust_score=composite,
        security_score=components["security"],
        components=components,
        positive_factors=positive,
        negative_factors=negative,
        blocking_conditions=blocking,
        promotion_eligible=eligible,
        evidence=evidence,
        explanation=explanation,
        evaluated_by="registry",
    )

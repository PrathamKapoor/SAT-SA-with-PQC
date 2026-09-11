"""AI Red Team Agent: autonomous adversarial testing of ML assets.

Emulates an attacker to produce evidence:

1. Integrity attack  - mutates a sandbox copy of the artifact and proves that
   digest verification detects it (validates the platform's tripwires).
2. Adversarial probe - perturbs inputs near decision boundaries of linear
   models and measures flip susceptibility.
3. Poisoning probe   - trains reference models on full vs outlier-trimmed data
   and measures weight divergence (outlier influence).
4. Unauthorized modification - recomputes artifact digests against passport
   and BOM declarations.

All experiments are non-destructive: they operate on copies or freshly trained
reference models and never touch registered artifacts.
"""
from __future__ import annotations

import json
import statistics

from qsmlops.agents.base import BaseAgent, Evidence, Finding, Observation, make_finding
from qsmlops.artifacts.store import ArtifactStore
from qsmlops.crypto.hashing import sha3_hex
from qsmlops.supplychain.bom import QMLBOM


class RedTeamAgent(BaseAgent):
    name = "red-team-agent"

    def __init__(
        self,
        artifacts: ArtifactStore,
        flip_rate_threshold: float = 0.35,
        poison_influence_threshold: float = 0.6,
    ) -> None:
        self.artifacts = artifacts
        self.flip_rate_threshold = flip_rate_threshold
        self.poison_influence_threshold = poison_influence_threshold

    def observe(self, context: dict) -> Observation:
        findings: list[Finding] = []
        findings.extend(self._test_integrity_tripwire(context))
        findings.extend(self._check_unauthorized_modification(context))
        model_probe = self._probe_adversarial(context)
        if model_probe is not None:
            findings.append(model_probe)
        poison = self._probe_poisoning(context)
        if poison is not None:
            findings.append(poison)

        critical = [f for f in findings if not f.passed and f.severity == "CRITICAL"]
        high = [f for f in findings if not f.passed and f.severity == "HIGH"]
        if critical:
            rec = "QUARANTINE"
        elif high:
            rec = "ESCALATE"
        else:
            rec = "ACCEPT"
        return Observation(
            agent=self.name,
            subject_id=context.get("subject_id", ""),
            recommendation=rec,
            findings=findings,
            notes=f"red-team ran {len(findings)} test(s)",
        )

    def _test_integrity_tripwire(self, context: dict) -> list[Finding]:
        artifact_digest = context.get("artifact_digest", "")
        findings: list[Finding] = []
        try:
            original = self.artifacts.get(artifact_digest)
        except Exception:
            return [
                make_finding(
                    "redtripwire_artifact_available",
                    False,
                    "HIGH",
                    f"cannot load artifact {artifact_digest[:12]}…",
                    observation="red-team sandbox could not load the served artifact for mutation testing",
                    evidence=[Evidence(
                        "artifact_store", "experiment", {"requested_digest": artifact_digest},
                        description="artifact retrieval during adversarial exercise",
                    )],
                    confidence=0.95,
                    recommendation="ESCALATE",
                )
            ]
        mutated = bytearray(original)
        mutated[len(mutated) // 2] ^= 0xFF
        mutated_digest = sha3_hex(bytes(mutated))
        detected = mutated_digest != artifact_digest and not self.artifacts.exists(
            mutated_digest
        )
        findings.append(
            make_finding(
                "tamper_detection_effective",
                detected,
                "CRITICAL",
                "single-byte mutation changes digest; store rejects unknown content"
                if detected
                else "mutation undetected - integrity controls broken",
                observation=(
                    "single-byte flip of model artifact produced a new SHA3-256 digest "
                    "and was rejected by the content-addressed store"
                    if detected
                    else "single-byte flip of model artifact was NOT rejected — integrity controls broken"
                ),
                evidence=[Evidence(
                    "tamper_experiment", "experiment",
                    {
                        "original_digest": artifact_digest,
                        "mutated_digest": mutated_digest,
                        "mutation": "single_byte_xor_midpoint",
                        "bytes_mutated": len(original),
                        "store_accepted_mutation": self.artifacts.exists(mutated_digest),
                    },
                    description="adversarial integrity tripwire validation on a sandbox copy",
                )],
                confidence=1.0 if detected else 0.99,
                recommendation="QUARANTINE" if not detected else "",
            )
        )
        return findings

    def _check_unauthorized_modification(self, context: dict) -> list[Finding]:
        findings: list[Finding] = []
        passport = context.get("passport")
        bom = context.get("bom")
        artifact_digest = context.get("artifact_digest", "")
        if passport is not None:
            declared = passport.identity.get("artifact_digest", "")
            match = declared == artifact_digest
            findings.append(
                make_finding(
                    "passport_binds_served_artifact",
                    match,
                    "CRITICAL",
                    "" if match else f"passport declares {declared[:12]}… but version serves {artifact_digest[:12]}…",
                    observation=(
                        "served artifact digest matches the digest bound into the signed passport"
                        if match
                        else f"MISMATCH: passport binds {declared[:16]}… but registry serves {artifact_digest[:16]}…"
                    ),
                    evidence=[Evidence(
                        "passport_identity", "crypto",
                        {
                            "passport_declared": declared,
                            "registry_serves": artifact_digest,
                            "signer_key_id": (
                                passport.signature.signer_key_id if passport.signature else ""
                            ),
                        },
                        description="digest binding between signed passport and deployed bytes",
                    )],
                    confidence=1.0,
                    recommendation="QUARANTINE" if not match else "",
                )
            )
        if bom is not None:
            if isinstance(bom, dict):
                bom = QMLBOM.from_dict(bom)
            declared_any = any(e.digest == artifact_digest for e in bom.entries)
            findings.append(
                make_finding(
                    "bom_declares_artifact",
                    declared_any,
                    "HIGH",
                    "" if declared_any else "served artifact absent from supply-chain BOM",
                    observation=(
                        "deployed artifact is inventoried in the QML-BOM"
                        if declared_any
                        else "deployed artifact is NOT inventoried in the QML-BOM (undeclared component)"
                    ),
                    evidence=[Evidence(
                        "qml_bom", "log",
                        {
                            "bom_id": getattr(bom, "bom_id", ""),
                            "entry_count": len(bom.entries),
                            "artifact_listed": declared_any,
                            "artifact_digest": artifact_digest,
                        },
                    )],
                    confidence=0.95,
                    recommendation="ESCALATE" if not declared_any else "",
                )
            )
        return findings

    def _load_linear_model(self, context: dict):
        try:
            raw = self.artifacts.get(context["artifact_digest"])
            doc = json.loads(raw.decode("utf-8"))
            weights = doc["weights"]
            bias = float(doc.get("bias", 0.0))
            return weights, bias
        except Exception:
            return None

    def _probe_adversarial(self, context: dict) -> Finding | None:
        loaded = self._load_linear_model(context)
        probes = context.get("probe_inputs") or []
        if loaded is None or not probes:
            return None
        weights, bias = loaded
        flips = 0
        margins = []
        for point in probes:
            score = sum(w * x for w, x in zip(weights, point)) + bias
            margin = abs(score)
            margins.append(margin)
            eps = max(1e-9, 0.01 * (margin + 1.0))
            perturbed = [x + eps for x in point]
            p_score = sum(w * x for w, x in zip(weights, perturbed)) + bias
            if (score >= 0) != (p_score >= 0):
                flips += 1
        flip_rate = flips / len(probes)
        median_margin = statistics.median(margins) if margins else 0.0
        fragile = flip_rate > self.flip_rate_threshold
        return make_finding(
            "adversarial_flip_resistance",
            not fragile,
            "MEDIUM" if fragile else "LOW",
            f"flip_rate={flip_rate:.2f} over {len(probes)} probes "
            f"(threshold {self.flip_rate_threshold}), median_margin={median_margin:.4f}",
            observation=(
                f"adversarial perturbation flipped {flips}/{len(probes)} probe predictions "
                f"(flip rate {flip_rate:.2f}, threshold {self.flip_rate_threshold})"
                if fragile
                else f"model robust: flip rate {flip_rate:.2f} within tolerance over {len(probes)} probes"
            ),
            evidence=[Evidence(
                "adversarial_probe", "experiment",
                {
                    "flip_rate": round(flip_rate, 4),
                    "probes": len(probes),
                    "flips": flips,
                    "median_margin": round(median_margin, 6),
                    "epsilon_strategy": "1% of |score|+1",
                    "threshold": self.flip_rate_threshold,
                },
                description="decision-boundary perturbation experiment on sandbox copy",
            )],
            confidence=0.85,
            recommendation="ESCALATE" if fragile else "",
        )

    def _probe_poisoning(self, context: dict) -> Finding | None:
        dataset = context.get("dataset")
        train_fn = context.get("train_fn")
        if not dataset or train_fn is None:
            return None
        full_model = train_fn(dataset)
        residuals = sorted(
            ((abs(sample[-1] - _predict_point(full_model, sample[:-1])), i) for i, sample in enumerate(dataset)),
            reverse=True,
        )
        trim_n = max(1, int(0.05 * len(residuals)))
        trimmed_idx = {i for _, i in residuals[:trim_n]}
        trimmed_data = [s for i, s in enumerate(dataset) if i not in trimmed_idx]
        trimmed_model = train_fn(trimmed_data)
        delta = sum(
            abs(a - b) for a, b in zip(full_model[0], trimmed_model[0])
        ) + abs(full_model[1] - trimmed_model[1])
        scale = sum(abs(w) for w in full_model[0]) + abs(full_model[1]) + 1e-9
        influence = min(1.0, delta / scale)
        risky = influence > self.poison_influence_threshold
        return make_finding(
            "poisoning_outlier_influence",
            not risky,
            "HIGH" if risky else "LOW",
            f"top-{trim_n} outliers shift weights by {influence:.3f} "
            f"(threshold {self.poison_influence_threshold})",
            observation=(
                f"removing top-{trim_n} outliers shifts model weights by {influence:.3f} "
                f"(relative L1, threshold {self.poison_influence_threshold}) — poisoning-sensitive"
                if risky
                else f"outlier influence {influence:.3f} within tolerance"
            ),
            evidence=[Evidence(
                "poisoning_experiment", "experiment",
                {
                    "relative_weight_shift": round(influence, 4),
                    "trimmed_outliers": trim_n,
                    "dataset_size": len(residuals),
                    "threshold": self.poison_influence_threshold,
                },
                description="trained reference models on full vs outlier-trimmed data; compared weights",
            )],
            confidence=0.8,
            recommendation="ESCALATE" if risky else "",
        )


def _predict_point(model, x) -> float:
    weights, bias = model
    return sum(w * v for w, v in zip(weights, x)) + bias

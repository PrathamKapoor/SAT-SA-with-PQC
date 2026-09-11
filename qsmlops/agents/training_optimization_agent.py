"""Training Optimization Agent (Phase 9).

Deterministic, evidence-bearing analysis of how a model was trained, using
only facts recorded at training time (passport ``training_info``), the
evaluation metrics, and the current drift summary. It never tunes anything
itself: it surfaces reproducibility / sample-adequacy / metadata-completeness
findings so the supervisor and operators can act through governed paths.
"""
from __future__ import annotations

from qsmlops.agents.base import BaseAgent, Evidence, Observation, make_finding


class TrainingOptimizationAgent(BaseAgent):
    name = "training-optimization-agent"

    MIN_SAMPLES_PER_FEATURE = 2  # classical adequacy heuristic

    def observe(self, context: dict) -> Observation:
        findings = []
        passport = context.get("passport")
        info = (getattr(passport, "training_info", {}) or {}) if passport else {}
        metrics = (getattr(passport, "metrics", {}) or {}) if passport else {}
        model_id = context.get("subject_id", "")

        # 1. metadata completeness ---------------------------------------
        required = ("algorithm", "framework", "dataset", "n_samples",
                    "hyperparameters")
        missing = [k for k in required if not info.get(k)]
        findings.append(make_finding(
            "training_metadata_complete",
            not missing,
            "MEDIUM",
            f"missing training metadata: {', '.join(missing)}" if missing
            else "algorithm/framework/dataset/hyperparameters recorded",
            observation=(f"training metadata incomplete ({', '.join(missing)} missing)"
                         if missing else "training metadata complete"),
            evidence=[Evidence("passport.training_info", "log",
                               {"present": [k for k in required if info.get(k)],
                                "missing": missing})],
            confidence=1.0,
            recommendation="MONITOR" if missing else "",
        ))

        # 2. reproducibility (seed recorded?) ----------------------------
        hp = info.get("hyperparameters") or {}
        has_seed = ("seed" in hp) or ("seed" in info)
        findings.append(make_finding(
            "training_reproducible_seed",
            has_seed,
            "MEDIUM",
            "" if has_seed else "no random seed recorded; retraining may diverge",
            observation=("random seed recorded; retraining reproducible"
                         if has_seed else
                         "training configuration lacks a recorded random seed"),
            evidence=[Evidence("passport.training_info.hyperparameters", "log",
                               {"has_seed": has_seed})],
            confidence=0.95,
            recommendation="" if has_seed else "RETRAIN_WITH_SEED",
        ))

        # 3. sample adequacy vs feature dimensionality --------------------
        n_samples = info.get("n_samples")
        ds_name = info.get("dataset")
        dataset = (context.get("datasets") or {}).get(ds_name)
        n_features = len(dataset.feature_names) if dataset else None
        if n_samples is None or n_features is None:
            findings.append(make_finding(
                "sample_adequacy", True, "LOW",
                "UNAVAILABLE: feature dimensionality unknown for this version",
                observation="sample adequacy not evaluable (feature count unavailable)",
                evidence=[Evidence("passport.training_info", "log",
                                   {"n_samples": n_samples,
                                    "n_features": n_features})],
                confidence=0.5,
            ))
        else:
            adequate = n_samples >= self.MIN_SAMPLES_PER_FEATURE * max(1, n_features)
            findings.append(make_finding(
                "sample_adequacy", adequate,
                "MEDIUM",
                "" if adequate else
                f"{n_samples} samples for {n_features} features "
                f"(< {self.MIN_SAMPLES_PER_FEATURE}x)",
                observation=(f"sample adequacy ok ({n_samples} >= "
                             f"{self.MIN_SAMPLES_PER_FEATURE * n_features})"
                             if adequate else
                             f"thin training set: {n_samples} samples vs "
                             f"{n_features} features"),
                evidence=[Evidence("passport.training_info", "metric",
                                   {"n_samples": n_samples,
                                    "n_features": n_features,
                                    "ratio": round(n_samples / max(1, n_features), 2)})],
                confidence=0.9,
                recommendation="COLLECT_MORE_DATA" if not adequate else "",
            ))

        # 4. drift-informed retraining hint -------------------------------
        drift = context.get("drift_summary") or {}
        if str(drift.get("max_severity")) in ("HIGH", "CRITICAL"):
            findings.append(make_finding(
                "retrain_data_refresh_warranted", False, "HIGH",
                f"drift {drift.get('max_severity')} suggests stale training data",
                observation="current data distribution diverged from training data",
                evidence=[Evidence("drift_engine", "distribution",
                                   {"max_severity": drift.get("max_severity"),
                                    "intelligence": drift.get("intelligence")})],
                confidence=0.9,
                recommendation="RETRAIN",
            ))

        failed = [f for f in findings if not f.passed]
        rec = "ACCEPT"
        if any(f.severity == "HIGH" for f in failed):
            rec = "RETRAIN"
        elif failed:
            rec = "MONITOR"
        return Observation(agent=self.name, subject_id=model_id,
                           recommendation=rec, findings=findings,
                           notes=f"evaluated {len(findings)} training-quality checks")

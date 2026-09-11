"""Advanced Drift Detection.
Implements PSI, KS-test, prediction drift, and performance drift detection.
"""
from __future__ import annotations

import json
import logging
import math
import warnings
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy import stats

try:
    from scipy.special import rel_entr
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    rel_entr = None


@dataclass
class DriftReport:
    drift_type: str
    affected_features: list[str]
    severity: str
    score: float
    threshold: float
    evidence: dict
    recommendation: str
    confidence: float = 1.0
    details: str = ""

    def to_dict(self) -> dict:
        return {
            "drift_type": self.drift_type,
            "affected_features": self.affected_features,
            "severity": self.severity,
            "score": self.score,
            "threshold": self.threshold,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "details": self.details,
        }


@dataclass
class DriftConfig:
    psi_threshold: float = 0.2
    ks_threshold: float = 0.05
    prediction_drift_threshold: float = 0.1
    performance_drift_threshold: float = 0.05
    min_samples: int = 100


class PSIDriftDetector:
    """Population Stability Index detector for feature drift."""
    
    def __init__(self, config: DriftConfig = None):
        self.config = config or DriftConfig()
    
    def compute_psi(self, expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
        """Compute Population Stability Index between two distributions."""
        if len(expected) == 0 or len(actual) == 0:
            return 0.0
        
        _, bin_edges = np.histogram(expected, bins=bins)
        expected_hist, _ = np.histogram(expected, bins=bin_edges)
        actual_hist, _ = np.histogram(actual, bins=bin_edges)
        
        expected_pct = expected_hist / len(expected)
        actual_pct = actual_hist / len(actual)
        
        expected_pct = np.where(expected_pct == 0, 1e-10, expected_pct)
        actual_pct = np.where(actual_pct == 0, 1e-10, actual_pct)
        
        psi = np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct))
        return float(psi)
    
    def detect(self, reference_data: np.ndarray, current_data: np.ndarray, 
               feature_names: list[str]) -> list[DriftReport]:
        reports = []
        n_features = min(reference_data.shape[1], current_data.shape[1])
        
        for i in range(n_features):
            psi_score = self.compute_psi(reference_data[:, i], current_data[:, i])
            feature_name = feature_names[i] if i < len(feature_names) else f"feature_{i}"

            # S4: a non-finite PSI means the score cannot be computed (NaN /
            # empty / corrupted columns). Do NOT fabricate a healthy "no drift"
            # result — surface it as an indeterminate MEDIUM signal instead.
            if not math.isfinite(psi_score):
                reports.append(DriftReport(
                    drift_type="feature_drift_psi_error",
                    affected_features=[feature_name],
                    severity="MEDIUM",
                    score=0.0,
                    threshold=self.config.psi_threshold,
                    evidence={"error": "non-finite PSI", "feature": feature_name},
                    recommendation="INVESTIGATE",
                    confidence=0.9,
                    details=f"PSI drift test produced a non-finite result for "
                            f"{feature_name!r}; treated as indeterminate",
                ))
                continue

            severity = "LOW"
            if psi_score > self.config.psi_threshold * 2:
                severity = "CRITICAL"
            elif psi_score > self.config.psi_threshold:
                severity = "HIGH"
            elif psi_score > self.config.psi_threshold * 0.5:
                severity = "MEDIUM"

            if psi_score > self.config.psi_threshold * 0.5:
                reports.append(DriftReport(
                    drift_type="feature_drift_psi",
                    affected_features=[feature_name],
                    severity=severity,
                    score=psi_score,
                    threshold=self.config.psi_threshold,
                    evidence={"psi": psi_score, "bins": 10},
                    recommendation="RETRAIN" if severity in ("HIGH", "CRITICAL") else "MONITOR",
                    confidence=0.9,
                    details=f"PSI={psi_score:.4f} for {feature_name} (threshold={self.config.psi_threshold})"
                ))

        return reports


class KSDriftDetector:
    """Kolmogorov-Smirnov test detector for feature drift."""
    
    def __init__(self, config: DriftConfig = None):
        self.config = config or DriftConfig()
    
    def detect(self, reference_data: np.ndarray, current_data: np.ndarray,
               feature_names: list[str]) -> list[DriftReport]:
        reports = []
        n_features = min(reference_data.shape[1], current_data.shape[1])
        
        for i in range(n_features):
            feature_name = feature_names[i] if i < len(feature_names) else f"feature_{i}"
            try:
                ks_stat, p_value = stats.ks_2samp(reference_data[:, i], current_data[:, i])
            except Exception:
                # S4: a failing KS test on a single feature must not silently
                # vanish; record it as an indeterminate MEDIUM signal so it
                # reaches get_summary -> alerting (fail-closed).
                reports.append(DriftReport(
                    drift_type="feature_drift_error",
                    affected_features=[feature_name],
                    severity="MEDIUM",
                    score=0.0,
                    threshold=self.config.ks_threshold,
                    evidence={"error": "KS test raised", "feature": feature_name},
                    recommendation="INVESTIGATE",
                    confidence=0.9,
                    details=f"KS drift test failed for feature {feature_name!r}; "
                            f"treated as indeterminate",
                ))
                continue

            # S4: non-finite KS output (e.g. NaN inputs) must not be read as a
            # clean "no drift" result — surface it as indeterminate MEDIUM.
            if not math.isfinite(p_value) or not math.isfinite(ks_stat):
                reports.append(DriftReport(
                    drift_type="feature_drift_error",
                    affected_features=[feature_name],
                    severity="MEDIUM",
                    score=0.0,
                    threshold=self.config.ks_threshold,
                    evidence={"error": "non-finite KS statistic", "feature": feature_name},
                    recommendation="INVESTIGATE",
                    confidence=0.9,
                    details=f"KS drift test produced a non-finite result for "
                            f"{feature_name!r}; treated as indeterminate",
                ))
                continue

            severity = "LOW"
            if p_value < self.config.ks_threshold / 10:
                severity = "CRITICAL"
            elif p_value < self.config.ks_threshold:
                severity = "HIGH"
            elif p_value < self.config.ks_threshold * 2:
                severity = "MEDIUM"

            if p_value < self.config.ks_threshold * 2:
                reports.append(DriftReport(
                    drift_type="feature_drift_ks",
                    affected_features=[feature_name],
                    severity=severity,
                    score=float(ks_stat),
                    threshold=self.config.ks_threshold,
                    evidence={"ks_statistic": float(ks_stat), "p_value": float(p_value)},
                    recommendation="RETRAIN" if severity in ("HIGH", "CRITICAL") else "MONITOR",
                    confidence=1.0 - p_value,
                    details=f"KS={ks_stat:.4f}, p={p_value:.4f} for {feature_name}"
                ))

        return reports


class PredictionDriftDetector:
    """Detects drift in model predictions."""
    
    def __init__(self, config: DriftConfig = None):
        self.config = config or DriftConfig()
    
    def detect(self, reference_predictions: np.ndarray, current_predictions: np.ndarray) -> list[DriftReport]:
        reports = []
        
        if len(reference_predictions) == 0 or len(current_predictions) == 0:
            return reports
        
        ks_stat, p_value = stats.ks_2samp(reference_predictions, current_predictions)
        
        severity = "LOW"
        if p_value < self.config.prediction_drift_threshold / 10:
            severity = "CRITICAL"
        elif p_value < self.config.prediction_drift_threshold:
            severity = "HIGH"
        elif p_value < self.config.prediction_drift_threshold * 2:
            severity = "MEDIUM"
        
        if p_value < self.config.prediction_drift_threshold * 2:
            reports.append(DriftReport(
                drift_type="prediction_drift",
                affected_features=["predictions"],
                severity=severity,
                score=float(ks_stat),
                threshold=self.config.prediction_drift_threshold,
                evidence={"ks_statistic": float(ks_stat), "p_value": float(p_value),
                          "ref_mean": float(np.mean(reference_predictions)),
                          "cur_mean": float(np.mean(current_predictions)),
                          "ref_std": float(np.std(reference_predictions)),
                          "cur_std": float(np.std(current_predictions))},
                recommendation="RETRAIN" if severity in ("HIGH", "CRITICAL") else "MONITOR",
                confidence=1.0 - p_value,
                details=f"Prediction distribution shift: KS={ks_stat:.4f}, p={p_value:.4f}"
            ))
        
        return reports


class PerformanceDriftDetector:
    """Detects drift in model performance metrics over time."""
    
    def __init__(self, config: DriftConfig = None):
        self.config = config or DriftConfig()
        self.performance_history: list[dict] = []
        self.window_size = 10
    
    def add_performance(self, metrics: dict):
        self.performance_history.append(metrics)
        if len(self.performance_history) > self.window_size * 2:
            self.performance_history = self.performance_history[-self.window_size:]
    
    def detect(self, current_metrics: dict, baseline_metrics: dict) -> list[DriftReport]:
        reports = []
        
        for metric_name in current_metrics:
            if metric_name not in baseline_metrics:
                continue
            
            current_val = current_metrics[metric_name]
            baseline_val = baseline_metrics[metric_name]
            
            if baseline_val == 0:
                continue
            
            relative_change = abs(current_val - baseline_val) / abs(baseline_val)
            
            severity = "LOW"
            if relative_change > self.config.performance_drift_threshold * 4:
                severity = "CRITICAL"
            elif relative_change > self.config.performance_drift_threshold * 2:
                severity = "HIGH"
            elif relative_change > self.config.performance_drift_threshold:
                severity = "MEDIUM"
            
            if relative_change > self.config.performance_drift_threshold:
                reports.append(DriftReport(
                    drift_type="performance_drift",
                    affected_features=[metric_name],
                    severity=severity,
                    score=relative_change,
                    threshold=self.config.performance_drift_threshold,
                    evidence={
                        "current": current_val,
                        "baseline": baseline_val,
                        "relative_change": relative_change
                    },
                    recommendation="RETRAIN" if severity in ("HIGH", "CRITICAL") else "MONITOR",
                    confidence=min(1.0, relative_change / self.config.performance_drift_threshold),
                    details=f"{metric_name} changed {relative_change*100:.1f}% from baseline"
                ))
        
        return reports


class DriftDetectionEngine:
    """Main drift detection orchestrator."""
    
    def __init__(self, config: DriftConfig = None):
        self.config = config or DriftConfig()
        self.psi_detector = PSIDriftDetector(config)
        self.ks_detector = KSDriftDetector(config)
        self.prediction_detector = PredictionDriftDetector(config)
        self.performance_detector = PerformanceDriftDetector(config)
        self.reference_data: Optional[np.ndarray] = None
        self.reference_predictions: Optional[np.ndarray] = None
        self.baseline_metrics: Optional[dict] = None
        self.feature_names: list[str] = []
    
    def set_reference(self, data: np.ndarray, predictions: np.ndarray = None, 
                      metrics: dict = None, feature_names: list[str] = None):
        self.reference_data = data
        self.reference_predictions = predictions
        self.baseline_metrics = metrics
        self.feature_names = feature_names or [f"feature_{i}" for i in range(data.shape[1])]
    
    def detect_all(self, current_data: np.ndarray, current_predictions: np.ndarray = None,
                   current_metrics: dict = None) -> list[DriftReport]:
        all_reports = []

        if self.reference_data is not None:
            ref = self.reference_data
            cur = np.asarray(current_data) if current_data is not None else None
            # S4: empty reference or current data cannot yield a valid drift
            # score. Do NOT report "healthy"; surface it as indeterminate MEDIUM
            # so monitoring alerts instead of silently passing (fail-closed).
            if ref.shape[0] == 0 or (cur is not None and cur.shape[0] == 0):
                all_reports.append(DriftReport(
                    drift_type="drift_indeterminate",
                    affected_features=[],
                    severity="MEDIUM",
                    score=0.0,
                    threshold=0.0,
                    evidence={"reason": "empty reference or current data"},
                    recommendation="INVESTIGATE",
                    confidence=1.0,
                    details="drift cannot be computed: empty reference or current data",
                ))
                return all_reports
            all_reports.extend(self.psi_detector.detect(
                ref, current_data, self.feature_names))
            all_reports.extend(self.ks_detector.detect(
                ref, current_data, self.feature_names))
        
        if self.reference_predictions is not None and current_predictions is not None:
            all_reports.extend(self.prediction_detector.detect(
                self.reference_predictions, current_predictions))
        
        if self.baseline_metrics is not None and current_metrics is not None:
            all_reports.extend(self.performance_detector.detect(
                current_metrics, self.baseline_metrics))
            self.performance_detector.add_performance(current_metrics)
        
        return all_reports
    
    def get_summary(self, reports: list[DriftReport]) -> dict:
        if not reports:
            return {"status": "STABLE", "max_severity": "NONE", "drift_count": 0}
        
        severities = [r.severity for r in reports]
        severity_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
        max_sev = max(severities, key=lambda s: severity_order.get(s, 0))
        
        return {
            "status": "DRIFT_DETECTED" if max_sev in ("HIGH", "CRITICAL") else "MONITOR",
            "max_severity": max_sev,
            "drift_count": len(reports),
            "by_type": {r.drift_type: len([x for x in reports if x.drift_type == r.drift_type]) for r in reports},
            "recommendations": list(set(r.recommendation for r in reports))
        }

# ----------------------------------------------------------------------
# Phase 8: feature attribution + drift intelligence
# ----------------------------------------------------------------------

_SEVERITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def build_feature_attribution(
    reports: list[DriftReport],
    reference_data=None,
    current_data=None,
    feature_names: Optional[list[str]] = None,
) -> list[dict]:
    """Attribute drift to individual features from existing detector output.

    Every detector report is already per-feature; this merges them into one
    attribution row per feature, ranked by severity then score. Baseline and
    current distribution statistics are computed from the actual arrays when
    the caller supplies them; otherwise they are reported as UNAVAILABLE
    rather than fabricated.
    """
    merged: dict[str, dict] = {}
    for r in reports:
        if not r.affected_features:
            continue
        feature = r.affected_features[0]
        row = merged.setdefault(feature, {
            "feature": feature,
            "detectors": [],
            "severity": "LOW",
            "score": 0.0,
            "threshold": r.threshold,
            "statistics": {},
            "sample_counts": {},
        })
        row["detectors"].append(r.drift_type)
        if _SEVERITY_ORDER.get(r.severity, 0) > _SEVERITY_ORDER.get(row["severity"], 0):
            row["severity"] = r.severity
        if abs(r.score) > abs(row["score"]):
            row["score"] = r.score
        row["statistics"].update({
            k: v for k, v in r.evidence.items() if isinstance(v, (int, float, str))
        })

    # real distribution statistics where the caller supplied arrays
    if reference_data is not None and current_data is not None:
        import numpy as _np

        names = feature_names or []
        for feature, row in merged.items():
            idx = None
            if feature in names:
                idx = names.index(feature)
            elif feature.startswith("feature_"):
                try:
                    idx = int(feature.split("_")[1])
                except ValueError:
                    idx = None
            if idx is None or idx >= reference_data.shape[1]:
                row["statistics"]["baseline_mean"] = "UNAVAILABLE"
                row["statistics"]["current_mean"] = "UNAVAILABLE"
                continue
            ref_col = _np.asarray(reference_data[:, idx], dtype=float)
            cur_col = _np.asarray(current_data[:, idx], dtype=float)
            row["statistics"]["baseline_mean"] = round(float(_np.mean(ref_col)), 6)
            row["statistics"]["current_mean"] = round(float(_np.mean(cur_col)), 6)
            row["sample_counts"] = {
                "reference": int(ref_col.size), "current": int(cur_col.size),
            }

    rows = sorted(
        merged.values(),
        key=lambda r: (-_SEVERITY_ORDER.get(r["severity"], 0), -abs(float(r["score"]))),
    )
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows


def classify_drift(
    *,
    attributions: list[dict],
    total_features: int,
    performance_degraded: bool = False,
    history_count: int | None = None,
    min_history: int = 3,
    broad_fraction: float = 0.5,
) -> str:
    """Deterministic interpretation of drift evidence (no heuristics beyond
    documented thresholds). Returns exactly one of:

        NO_DRIFT | ISOLATED_FEATURE_DRIFT | BROAD_FEATURE_DRIFT |
        PERFORMANCE_DEGRADATION | DRIFT_WITH_PERFORMANCE_DEGRADATION |
        INSUFFICIENT_HISTORY
    """
    insufficient = history_count is not None and history_count < min_history
    features_drifting = sorted({a["feature"] for a in attributions})

    if not features_drifting:
        if insufficient and not performance_degraded:
            return "INSUFFICIENT_HISTORY"
        return "PERFORMANCE_DEGRADATION" if performance_degraded else (
            "INSUFFICIENT_HISTORY" if insufficient else "NO_DRIFT")

    broad_cutoff = max(2, int(round(broad_fraction * max(1, total_features))))
    broad = len(features_drifting) >= broad_cutoff

    if performance_degraded:
        return "DRIFT_WITH_PERFORMANCE_DEGRADATION"
    return "BROAD_FEATURE_DRIFT" if broad else "ISOLATED_FEATURE_DRIFT"

"""ML Performance Agent: evaluates model metrics against deployment thresholds.

Phase 2 upgrades:
- consumes structured DriftReports from qsmlops.ml.drift (PSI / KS / prediction
  / performance drift) supplied by the monitoring loop;
- evaluates rolling-window production metrics against the training baseline;
- every finding carries observation, evidence, confidence, risk and a
  recommended action (e.g. RETRAIN).
"""
from __future__ import annotations

import statistics

from qsmlops.agents.base import BaseAgent, Evidence, Finding, Observation, make_finding
from qsmlops.config import DEFAULT_METRIC_THRESHOLDS

SEVERITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


class PerformanceAgent(BaseAgent):
    name = "ml-performance-agent"

    def __init__(self, thresholds: dict | None = None) -> None:
        self.thresholds = dict(DEFAULT_METRIC_THRESHOLDS)
        if thresholds:
            self.thresholds.update(thresholds)

    # ------------------------------------------------------------------
    def observe(self, context: dict) -> Observation:
        findings: list[Finding] = []
        findings.extend(self._check_reported_metrics(context))
        findings.extend(self._check_rolling_metrics(context))
        findings.extend(self._check_drift_reports(context))

        hard_fail = any(
            (not f.passed and f.severity == "HIGH") for f in findings
        )
        critical_drift = any(
            not f.passed and f.severity == "CRITICAL"
            for f in findings
            if f.name.startswith("drift_")
        )
        if critical_drift:
            rec = "ROLLBACK"
        elif hard_fail:
            rec = "RETRAIN"
        else:
            rec = "ACCEPT"
        return Observation(
            agent=self.name,
            subject_id=context.get("subject_id", ""),
            recommendation=rec,
            findings=findings,
        )

    # ------------------------------------------------------------------
    def _check_reported_metrics(self, context: dict) -> list[Finding]:
        metrics = context.get("metrics", {})
        findings: list[Finding] = []
        r2 = metrics.get("r2")
        mse = metrics.get("mse")
        if r2 is None or mse is None:
            findings.append(
                make_finding(
                    "metrics_reported",
                    False,
                    "HIGH",
                    "missing r2/mse in evaluation",
                    observation="model evaluation did not report r2/mse",
                    evidence=[Evidence("evaluation_pipeline", "metric", dict(metrics))],
                    confidence=0.99,
                    recommendation="ESCALATE",
                )
            )
            return findings
        findings.append(
            make_finding(
                "r2_above_threshold",
                r2 >= self.thresholds["min_r2"],
                "HIGH",
                f"r2={r2:.4f} threshold={self.thresholds['min_r2']}",
                observation=f"coefficient of determination r2={r2:.4f} vs required {self.thresholds['min_r2']:.4f}",
                evidence=[Evidence(
                    "passport_metrics", "metric",
                    {"r2": r2, "threshold": self.thresholds["min_r2"]},
                )],
                confidence=0.97,
                recommendation="RETRAIN",
            )
        )
        findings.append(
            make_finding(
                "mse_below_threshold",
                mse <= self.thresholds["max_mse"],
                "MEDIUM",
                f"mse={mse:.4f} threshold={self.thresholds['max_mse']}",
                observation=f"mean squared error {mse:.4f} vs allowed maximum {self.thresholds['max_mse']:.4f}",
                evidence=[Evidence(
                    "passport_metrics", "metric",
                    {"mse": mse, "threshold": self.thresholds["max_mse"]},
                )],
                confidence=0.97,
                recommendation="RETRAIN",
            )
        )
        return findings

    # ------------------------------------------------------------------
    def _check_rolling_metrics(self, context: dict) -> list[Finding]:
        """Compare rolling production window against the training baseline."""
        rolling = context.get("rolling_metrics") or {}
        window = rolling.get("window") or []
        baseline = rolling.get("baseline") or {}
        if not window or not baseline:
            return []
        findings: list[Finding] = []
        for metric_name, baseline_val in baseline.items():
            values = [w[metric_name] for w in window if metric_name in w]
            if len(values) < 2:
                continue
            current = statistics.fmean(values)
            direction_bad = metric_name.startswith(("mse", "loss", "mae"))
            delta = current - baseline_val
            rel_change = abs(delta) / max(abs(baseline_val), 1e-9)
            worse = (delta > 0) == direction_bad
            dropped_pct = abs(delta) * 100
            sev = "LOW"
            if worse and rel_change >= 0.30:
                sev = "CRITICAL"
            elif worse and rel_change >= 0.15:
                sev = "HIGH"
            elif worse and rel_change >= 0.05:
                sev = "MEDIUM"
            passed = not worse or rel_change < 0.05
            findings.append(
                make_finding(
                    f"rolling_{metric_name}_stable",
                    passed,
                    sev,
                    f"rolling mean {metric_name}={current:.4f} vs baseline "
                    f"{baseline_val:.4f} ({delta:+.4f}, {dropped_pct:.1f}%)",
                    observation=(
                        f"{metric_name} degraded {dropped_pct:.1f}% over rolling "
                        f"window of {len(values)} evaluation(s)"
                        if not passed
                        else f"{metric_name} stable within tolerance over {len(values)} evaluation(s)"
                    ),
                    evidence=[
                        Evidence(
                            "rolling_metrics_window",
                            "metric",
                            {
                                "metric": metric_name,
                                "window_values": [round(v, 6) for v in values],
                                "window_mean": round(current, 6),
                                "baseline": baseline_val,
                                "absolute_delta": round(delta, 6),
                                "relative_change": round(rel_change, 4),
                                "direction": "worse" if worse else "better",
                            },
                            description=f"rolling accuracy/error window for {metric_name}",
                        ),
                        Evidence(
                            "training_baseline",
                            "metric",
                            {"metrics": dict(baseline)},
                            description="baseline recorded at training time",
                        ),
                    ],
                    confidence=min(0.95, 0.7 + rel_change),
                    recommendation="RETRAIN" if sev in ("HIGH", "CRITICAL") else ("MONITOR" if not passed else ""),
                )
            )
        return findings

    # ------------------------------------------------------------------
    def _check_drift_reports(self, context: dict) -> list[Finding]:
        reports = context.get("drift_reports") or []
        findings: list[Finding] = []
        # Legacy flag support: boolean drift_detected without structured reports
        if not reports and context.get("drift_detected"):
            findings.append(
                make_finding(
                    "input_distribution_stable",
                    False,
                    "MEDIUM",
                    "input drift detected",
                    observation="monitoring loop flagged input distribution instability",
                    evidence=[Evidence(
                        "monitoring_loop", "distribution", {"drift_detected": True},
                        description="legacy boolean drift signal",
                    )],
                    confidence=0.75,
                    recommendation="MONITOR",
                )
            )
            return findings
        for rpt in reports:
            d = rpt if isinstance(rpt, dict) else rpt.to_dict()
            sev = str(d.get("severity", "LOW")).upper()
            if sev == "NONE":
                continue
            drift_type = d.get("drift_type", "unknown")
            features = d.get("affected_features", [])
            score = float(d.get("score", 0.0))
            threshold = float(d.get("threshold", 0.0))
            finding_sev = sev if sev in SEVERITY_ORDER else "MEDIUM"
            findings.append(
                make_finding(
                    f"drift_{drift_type}",
                    False,
                    finding_sev,
                    d.get("details", f"{drift_type} on {features}: score={score:.4f}"),
                    observation=(
                        f"{drift_type} detected on {', '.join(map(str, features)) or 'unknown'} "
                        f"(severity {finding_sev}, score {score:.4f} vs threshold {threshold:.4f})"
                    ),
                    evidence=[
                        Evidence(
                            f"drift_engine:{drift_type}",
                            "distribution",
                            dict(d.get("evidence", {})),
                            description=d.get("details", ""),
                        ),
                        Evidence(
                            "drift_report_meta",
                            "distribution",
                            {
                                "drift_type": drift_type,
                                "affected_features": features,
                                "score": score,
                                "threshold": threshold,
                                "detector_confidence": d.get("confidence", 1.0),
                            },
                        ),
                    ],
                    confidence=float(d.get("confidence", 0.9)),
                    recommendation=d.get("recommendation", "MONITOR"),
                )
            )
        return findings

"""Alert evaluation for the monitoring foundation (Phase 7).

Deterministic rule evaluation over evidence the platform already produces:
recorded model metrics (against the deployment thresholds used everywhere
else), drift-engine summaries, and trust decisions. No external alerting
infrastructure is invented here; alerts are structured records an operator
or the API can consume.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from qsmlops.config import DEFAULT_METRIC_THRESHOLDS

_LEVELS = ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL")

_DRIFT_ALERT = {
    "CRITICAL": ("CRITICAL", "DRIFT_CRITICAL"),
    "HIGH": ("HIGH", "DRIFT_HIGH"),
    "MEDIUM": ("MEDIUM", "DRIFT_MEDIUM"),
}

_TRUST_ALERT = {
    "BLOCKED": ("CRITICAL", "TRUST_BLOCKED"),
    "QUARANTINED": ("CRITICAL", "TRUST_QUARANTINED"),
    "REVIEW_REQUIRED": ("HIGH", "TRUST_REVIEW_REQUIRED"),
}


@dataclass
class Alert:
    level: str
    code: str
    model_id: str
    detail: str = ""
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {"level": self.level, "code": self.code,
                "model_id": self.model_id, "detail": self.detail,
                "ts": self.ts}


def evaluate(
    model_id: str,
    metrics: dict | None = None,
    drift_summary: dict | None = None,
    trust_decision: str | None = None,
    thresholds: dict | None = None,
    feature_attributions: list[dict] | None = None,
    rolling_baselines: list[dict] | None = None,
) -> list[Alert]:
    """Evaluate monitoring rules; returns open alerts (empty == healthy)."""
    thresholds = {**DEFAULT_METRIC_THRESHOLDS, **(thresholds or {})}
    metrics = metrics or {}
    alerts: list[Alert] = []

    r2 = metrics.get("r2")
    mse = metrics.get("mse")
    r2_bad = r2 is not None and math.isfinite(r2) and r2 < thresholds["min_r2"]
    mse_bad = mse is not None and math.isfinite(mse) and mse > thresholds["max_mse"]
    # C3: a negative MSE is mathematically impossible and must NOT be read as
    # healthy — emit a fail-closed PERFORMANCE_DEGRADED alert (HIGH unless a
    # genuine critical degradation is also present).
    mse_negative = mse is not None and math.isfinite(mse) and mse < 0
    if r2_bad or mse_bad or mse_negative:
        level = "CRITICAL" if (r2_bad and mse_bad) else "HIGH"
        alerts.append(Alert(
            level, "PERFORMANCE_DEGRADED", model_id,
            detail=(f"r2={r2} (min {thresholds['min_r2']}), "
                    f"mse={mse} (max {thresholds['max_mse']})"
                    + ("; NEGATIVE MSE is invalid" if mse_negative else "")),
        ))
    if (r2 is not None and not math.isfinite(r2)) or (mse is not None and not math.isfinite(mse)):
        # Non-finite metrics are a real degradation signal — alert rather
        # than silently passing (fail-closed).
        alerts.append(Alert(
            "HIGH", "PERFORMANCE_DEGRADED", model_id,
            detail=f"non-finite metric value (r2={r2}, mse={mse})",
        ))

    sev = str((drift_summary or {}).get("max_severity", "NONE")).upper()
    if sev in _DRIFT_ALERT:
        level, code = _DRIFT_ALERT[sev]
        alerts.append(Alert(level, code, model_id, detail=json_detail(drift_summary)))

    if trust_decision in _TRUST_ALERT:
        level, code = _TRUST_ALERT[trust_decision]
        alerts.append(Alert(level, code, model_id,
                            detail=f"trust decision {trust_decision}"))

    # Phase 8: feature-level and sustained-degradation distinctions.
    for row in feature_attributions or []:
        if row.get("severity") == "CRITICAL":
            alerts.append(Alert(
                "CRITICAL", "FEATURE_DRIFT_CRITICAL", model_id,
                detail=f"feature {row['feature']} drifted (score={row.get('score')})",
            ))
    if (drift_summary or {}).get("intelligence") == "BROAD_FEATURE_DRIFT":
        alerts.append(Alert("HIGH", "FEATURE_DRIFT_BROAD", model_id,
                            detail="broad multi-feature drift"))
    for rb in rolling_baselines or []:
        if rb.get("sufficient") and rb.get("degraded") and rb.get("relative_change", 0) >= 0.15:
            alerts.append(Alert(
                "HIGH", "SUSTAINED_PERFORMANCE_DEGRADATION", model_id,
                detail=(f"{rb['metric']}: recent mean {rb['recent_mean']} vs prior "
                        f"{rb['prior_mean']} ({rb['relative_change']*100:.1f}% worse "
                        f"over {rb['window']} observations)"),
            ))

    return alerts


def json_detail(summary: dict | None) -> str:
    import json as _json

    try:
        return _json.dumps(summary or {}, sort_keys=True)
    except (TypeError, ValueError):
        return str(summary)


def worst_level(alerts: list[Alert]) -> str:
    """Highest severity present, or 'NONE'."""
    order = {lvl: i for i, lvl in enumerate(_LEVELS)}
    worst = "NONE"
    for a in alerts:
        if order.get(a.level, -1) > order.get(worst, -1):
            worst = a.level
    return worst

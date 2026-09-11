"""Telemetry collection for the monitoring foundation (Phase 7).

A minimal, dependency-free time-series store: newline-delimited JSON records
appended under ``<home>/monitoring/telemetry.jsonl``. This is the Tier-3
development store described by the architecture document's database policy;
production deployments are expected to swap in a quantum-secured time-series
backend behind this same interface.

Records::

    {"ts": ..., "model_id": ..., "kind": "...", "name": "...",
     "value": ..., "source": "...", "detail": {...}}
"""
from __future__ import annotations

import json
import math
import statistics
import threading
import time
from pathlib import Path


class TelemetryCollector:
    """Append-only telemetry store with query helpers."""

    def __init__(self, store_path: Path) -> None:
        self.path = Path(store_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    def record(
        self,
        model_id: str,
        kind: str,
        name: str,
        value: float | None = None,
        source: str = "platform",
        detail: dict | None = None,
    ) -> dict:
        entry = {
            "ts": time.time(),
            "model_id": model_id,
            "kind": kind,
            "name": name,
            "value": value,
            "source": source,
            "detail": detail or {},
        }
        with self._lock:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, sort_keys=True) + "\n")
        return entry

    def record_model_health(
        self,
        model_id: str,
        metrics: dict,
        source: str = "health_check",
        extra: dict | None = None,
    ) -> int:
        """Persist every numeric metric from a health observation."""
        n = 0
        for name, value in (metrics or {}).items():
            if isinstance(value, (int, float)) and math.isfinite(value):
                self.record(model_id, "metric", name, float(value), source,
                            detail=extra or {})
                n += 1
        return n

    def record_drift(self, model_id: str, drift_summary: dict | None) -> dict | None:
        if not drift_summary:
            return None
        return self.record(
            model_id,
            "drift",
            str(drift_summary.get("max_severity", "NONE")),
            float(drift_summary.get("drift_count", 0)),
            source="drift_engine",
            detail=dict(drift_summary),
        )

    # ------------------------------------------------------------------
    def _entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        continue
        return out

    def iter_entries(self, model_id: str | None = None, kind: str | None = None):
        for e in self._entries():
            if model_id is not None and e.get("model_id") != model_id:
                continue
            if kind is not None and e.get("kind") != kind:
                continue
            yield e

    def series(self, model_id: str, name: str) -> list[dict]:
        return [e for e in self.iter_entries(model_id, "metric")
                if e.get("name") == name]

    def latest(self, model_id: str, name: str) -> dict | None:
        s = self.series(model_id, name)
        return s[-1] if s else None

    def summary(self, model_id: str) -> dict:
        """Per-metric rolling summary over everything recorded."""
        by_name: dict[str, list[float]] = {}
        for e in self.iter_entries(model_id, "metric"):
            v = e.get("value")
            if isinstance(v, (int, float)):
                by_name.setdefault(e["name"], []).append(float(v))
        out = {}
        for name, values in sorted(by_name.items()):
            out[name] = {
                "count": len(values),
                "last": values[-1],
                "min": min(values),
                "max": max(values),
                "mean": round(statistics.fmean(values), 6),
            }
        return out

    def drift_history(self, model_id: str) -> list[dict]:
        return list(self.iter_entries(model_id, "drift"))

    # ------------------------------------------------------------------
    def feature_history(self, model_id: str) -> list[dict]:
        """All persisted per-feature drift attributions (Phase 8)."""
        return list(self.iter_entries(model_id, "feature_drift"))

    def latest_feature_attribution(self, model_id: str) -> list[dict]:
        """Attribution rows from the most recent drift check, ranked."""
        rows = self.feature_history(model_id)
        if not rows:
            return []
        last_check = rows[-1]["detail"].get("check_ts")
        latest = [r for r in rows if r["detail"].get("check_ts") == last_check]
        return sorted(latest, key=lambda r: r["detail"].get("rank", 999))

    def record_feature_attribution(
        self, model_id: str, attribution_rows: list[dict], source: str = "drift_engine",
    ) -> int:
        """Persist one row per drifting feature (Phase 8)."""
        n = 0
        check_ts = time.time()
        for row in attribution_rows:
            self.record(
                model_id,
                "feature_drift",
                row["feature"],
                float(row.get("score", 0.0)),
                source=source,
                detail={**row, "check_ts": check_ts},
            )
            n += 1
        return n

    def rolling_baseline(
        self,
        model_id: str,
        metric: str,
        window: int = 10,
        min_history: int = 3,
        worse_direction: str = "auto",
    ) -> dict:
        """Rolling-window performance baseline from recorded telemetry.

        Compares the most recent ``window`` observations against the prior
        history of the same metric (both from this single store).
        """
        series = [e["value"] for e in self.series(model_id, metric)]
        total = len(series)
        if total < min_history:
            return {
                "metric": metric, "observations": total,
                "sufficient": False,
                "reason": f"need >= {min_history} observations, have {total}",
                "window": window,
            }
        recent = series[-window:] if window > 0 else series[:]
        prior = series[:-window] if window > 0 else []
        # T4: the baseline is sufficient only when the PRIOR history (the
        # observations lying outside the recent window) holds at least
        # `min_history` points. This accounts for the recent window, the prior
        # window and min_history together, instead of merely requiring "any"
        # prior observation. The recent window is used for the comparison; the
        # prior window is the reference baseline.
        if len(prior) < min_history:
            # Not enough prior history to build a baseline: cannot assess
            # degradation, so the baseline is explicitly NOT sufficient
            # (fail-closed rather than falsely reporting "healthy").
            return {
                "metric": metric,
                "observations": total,
                "window": len(recent),
                "sufficient": False,
                "reason": (
                    f"need >= {min_history} prior observations (outside the "
                    f"recent window of {len(recent)}) to establish a baseline; "
                    f"have {len(prior)}"
                ),
            }
        recent_mean = statistics.fmean(recent)
        prior_mean = statistics.fmean(prior)
        delta = recent_mean - prior_mean
        rel_change = (abs(delta) / abs(prior_mean)) if prior_mean else 0.0
        if worse_direction == "auto":
            worse = (delta > 0) if metric.startswith(("mse", "loss", "mae", "error")) else (delta < 0)
        else:
            worse = {"up": delta > 0, "down": delta < 0}.get(worse_direction, False)
        return {
            "metric": metric,
            "observations": total,
            "window": len(recent),
            "recent_mean": round(recent_mean, 6),
            "prior_mean": round(prior_mean, 6),
            "delta": round(delta, 6),
            "relative_change": round(rel_change, 6),
            "direction": "worse" if worse else ("better" if delta != 0 else "flat"),
            "sufficient": True,
            "degraded": bool(worse and prior and rel_change > 0),
        }

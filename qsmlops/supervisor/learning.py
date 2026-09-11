"""Adaptive learning store for the supervisor.

Records every decision outcome and adapts behavior: models with repeated
failed auto-recovery attempts are escalated to humans instead of retried
endlessly. Feedback can also mark decisions as false positives, which decays
future risk inflation from similar findings.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional


class LearningStore:
    def __init__(self, path: Path, max_consecutive_failures: int = 2) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_consecutive_failures = max_consecutive_failures
        self._state = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return {"outcomes": [], "consecutive_failures": {}, "false_positives": {}}

    def _save(self) -> None:
        self.path.write_text(
            json.dumps(self._state, indent=2, sort_keys=True), encoding="utf-8"
        )

    def record_outcome(self, model_name: str, decision: str, success: bool, detail: str = "") -> None:
        self._state["outcomes"].append(
            {
                "model": model_name,
                "decision": decision,
                "success": success,
                "detail": detail,
                "at": time.time(),
            }
        )
        key = model_name
        streaks = self._state["consecutive_failures"]
        if success:
            streaks[key] = 0
        else:
            streaks[key] = streaks.get(key, 0) + 1
        self._save()

    def consecutive_failures(self, model_name: str) -> int:
        return self._state["consecutive_failures"].get(model_name, 0)

    def should_escalate(self, model_name: str) -> bool:
        return self.consecutive_failures(model_name) >= self.max_consecutive_failures

    def report_false_positive(self, finding_name: str) -> None:
        counts = self._state["false_positives"]
        counts[finding_name] = counts.get(finding_name, 0) + 1
        self._save()

    def false_positive_count(self, finding_name: str) -> int:
        return self._state["false_positives"].get(finding_name, 0)

    @property
    def total_outcomes(self) -> int:
        return len(self._state["outcomes"])

    def summary(self) -> dict:
        outcomes = self._state["outcomes"]
        successes = sum(1 for o in outcomes if o["success"])
        return {
            "total_decisions": len(outcomes),
            "successes": successes,
            "failures": len(outcomes) - successes,
            "hot_models": {
                k: v for k, v in self._state["consecutive_failures"].items() if v > 0
            },
        }

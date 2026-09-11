"""Build the SAT-SA demo dataset — five small, hand-crafted CSE
submissions exercising every analytics rule (execution gaps,
negative space, anomaly, peer deviation), plus a separate
ground-truth file that an evaluator can compare against the
analytics output.

Run with::

    python scripts/build_demo_dataset.py

This script writes the submission directories to
``docs/demo/submissions/<CSE_ID>/*`` and the ground truth to
``docs/demo/ground-truth.json``. The committed dataset is
reproducible: the same script run on a clean tree produces the
same files (the only randomness is the new_id() values, which
the platform substitutes on ingestion).

Five CSEs:
  * CSE-HEALTHY  — all clean metrics; should produce only
                    'no-signal' / 'insufficient-data' / non-actionable
                    findings.
  * CSE-EXEC     — fast closures + missing investigations +
                    metric gaming; should produce execution_gap +
                    potential_metric_gaming signals.
  * CSE-NEG      — critical assets with zero alerts + no
                    dispositions; should produce negative_space +
                    missing_monitoring signals.
  * CSE-ANOM     — one extreme outlier across the metric
                    distribution; should produce anomaly findings.
  * CSE-PEER     — closes in 30s while peers close in 30 min;
                    should produce peer_benchmark.deviation signals.

All five share the same assessment period and sector so they
form a real peer cohort.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

PERIOD_START = 1735689600.0  # 2025-01-01T00:00:00Z
PERIOD_END = 1738281600.0    # 2025-02-01T00:00:00Z
SECTOR = "defence"
ENV = "on-prem"


def _write_submission(directory: Path, files: dict[str, str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (directory / name).write_text(content, encoding="utf-8")


def healthy_cse(directory: Path) -> None:
    """All healthy: 2 critical alerts closed at 2h with 3-step
    investigations; 2 high closed at 4h; 1 medium closed at 6h.
    No peer-deviation, no anomaly, no negative space."""
    files = {
        "assets.csv": "native_id,criticality,environment,controls\n"
                      "web-01,critical,prod,AV;EDR\n"
                      "db-01,high,prod,DB-FW\n",
        "alerts.csv": "native_id,created_at,severity,acknowledged_at,closed_at,case_ids,asset_ids\n"
                      f"A1,{PERIOD_START + 600},critical,{PERIOD_START + 1200},{PERIOD_START + 7200},C1,web-01\n"
                      f"A2,{PERIOD_START + 1200},high,{PERIOD_START + 1800},{PERIOD_START + 14400},C2,db-01\n"
                      f"A3,{PERIOD_START + 1800},medium,{PERIOD_START + 2400},{PERIOD_START + 21600},C2,db-01\n",
        "cases.csv": "native_id,opened_at,status,closed_at,owner,alert_ids,closure_reason\n"
                     f"C1,{PERIOD_START + 500},closed,{PERIOD_START + 7200},alice,A1,resolved\n"
                     f"C2,{PERIOD_START + 1100},closed,{PERIOD_START + 14400},bob,A2;A3,resolved\n",
        "investigation_steps.csv": "case_id,action_type,performed_at,sequence,analyst,note,evidence_ids\n"
                                  f"C1,triage,{PERIOD_START + 700},1,alice,initial triage per runbook,EV-1\n"
                                  f"C1,containment,{PERIOD_START + 2000},2,alice,host isolated,EV-2\n"
                                  f"C1,recovery,{PERIOD_START + 5000},3,alice,restored from backup,EV-3\n"
                                  f"C2,triage,{PERIOD_START + 1300},1,bob,reviewed indicators,bob-EV-1\n"
                                  f"C2,containment,{PERIOD_START + 4000},2,bob,patched,EV-2\n"
                                  f"C2,recovery,{PERIOD_START + 9000},3,bob,monitored,bob-EV-3\n",
        "escalations.csv": "alert_id,case_id,occurred_at,destination_role,trigger,outcome\n"
                           f"A1,C1,{PERIOD_START + 1500},soc-l2,severity critical,acknowledged\n"
                           f"A2,C2,{PERIOD_START + 2000},soc-l2,severity high,acknowledged\n",
        "dispositions.csv": "alert_id,case_id,occurred_at,outcome,reason,approver_role\n"
                           f"A1,C1,{PERIOD_START + 7000},true_positive,confirmed malware,soc-lead\n"
                           f"A2,C2,{PERIOD_START + 14000},true_positive,confirmed intrusion,soc-lead\n"
                           f"A3,C2,{PERIOD_START + 21000},benign,suppressed noise,soc-lead\n",
    }
    _write_submission(directory, files)


def exec_gap_cse(directory: Path) -> None:
    """Execution gap profile: two critical alerts closed in <10
    minutes with no investigation, one critical with no
    escalation, a repeated alert into a no-remediation case,
    plus a metric-gaming shape (100% closure, 0-1 step per case)."""
    files = {
        "assets.csv": "native_id,criticality,environment,controls\n"
                      "srv-01,critical,prod,AV\n",
        "alerts.csv": "native_id,created_at,severity,acknowledged_at,closed_at,case_ids,asset_ids\n"
                      f"A1,{PERIOD_START + 100},critical,{PERIOD_START + 200},{PERIOD_START + 300},C1,srv-01\n"
                      f"A2,{PERIOD_START + 200},critical,{PERIOD_START + 300},{PERIOD_START + 500},C1,srv-01\n"
                      f"A3,{PERIOD_START + 300},critical,{PERIOD_START + 400},{PERIOD_START + 600},C2,srv-01\n"
                      f"A4,{PERIOD_START + 400},high,{PERIOD_START + 500},{PERIOD_START + 700},C3,srv-01\n"
                      f"A5,{PERIOD_START + 500},high,{PERIOD_START + 600},{PERIOD_START + 800},C3,srv-01\n"
                      f"A6,{PERIOD_START + 600},medium,{PERIOD_START + 700},{PERIOD_START + 900},C4,srv-01\n"
                      f"A7,{PERIOD_START + 700},medium,{PERIOD_START + 800},{PERIOD_START + 1000},C4,srv-01\n"
                      f"A8,{PERIOD_START + 800},medium,{PERIOD_START + 900},{PERIOD_START + 1100},C4,srv-01\n"
                      f"A9,{PERIOD_START + 900},medium,{PERIOD_START + 1000},{PERIOD_START + 1200},C4,srv-01\n"
                      f"A10,{PERIOD_START + 1000},medium,{PERIOD_START + 1100},{PERIOD_START + 1300},C4,srv-01\n",
        "cases.csv": "native_id,opened_at,status,closed_at,owner,alert_ids,closure_reason\n"
                     f"C1,{PERIOD_START + 150},closed,{PERIOD_START + 600},alice,A1;A2,resolved\n"
                     f"C2,{PERIOD_START + 350},closed,{PERIOD_START + 700},bob,A3,resolved\n"
                     f"C3,{PERIOD_START + 450},closed,{PERIOD_START + 900},alice,A4;A5,resolved\n"
                     f"C4,{PERIOD_START + 650},closed,{PERIOD_START + 1400},bob,A6;A7;A8;A9;A10,resolved\n",
        "investigation_steps.csv": "case_id,action_type,performed_at,sequence,analyst,note,evidence_ids\n"
                                  f"C1,triage,{PERIOD_START + 200},1,alice,ok,EV-1\n"
                                  f"C2,triage,{PERIOD_START + 400},1,bob,ok,EV-2\n"
                                  f"C3,triage,{PERIOD_START + 500},1,alice,ok,EV-3\n"
                                  f"C4,triage,{PERIOD_START + 700},1,bob,ok,EV-4\n",
        "escalations.csv": "alert_id,case_id,occurred_at,destination_role,trigger,outcome\n"
                           f"A3,C2,{PERIOD_START + 500},soc-l2,severity critical,acknowledged\n",
        "dispositions.csv": "alert_id,case_id,occurred_at,outcome,reason,approver_role\n"
                           f"A1,C1,{PERIOD_START + 500},false_positive,ok,alice\n"
                           f"A2,C1,{PERIOD_START + 500},false_positive,ok,alice\n"
                           f"A3,C2,{PERIOD_START + 600},true_positive,ok,bob\n"
                           f"A4,C3,{PERIOD_START + 800},false_positive,ok,alice\n"
                           f"A5,C3,{PERIOD_START + 800},false_positive,ok,alice\n"
                           f"A6,C4,{PERIOD_START + 1200},benign,ok,bob\n"
                           f"A7,C4,{PERIOD_START + 1200},benign,ok,bob\n"
                           f"A8,C4,{PERIOD_START + 1200},benign,ok,bob\n"
                           f"A9,C4,{PERIOD_START + 1200},benign,ok,bob\n"
                           f"A10,C4,{PERIOD_START + 1200},benign,ok,bob\n",
    }
    _write_submission(directory, files)


def negative_space_cse(directory: Path) -> None:
    """Negative-space profile: critical assets with zero alerts
    (monitoring gap), closed cases with no investigation, no
    disposition on closed alerts."""
    files = {
        "assets.csv": "native_id,criticality,environment,controls\n"
                      "core-01,critical,prod,AV;EDR\n"
                      "core-02,critical,prod,AV;EDR\n"
                      "edge-01,critical,prod,FW\n"
                      "edge-02,high,prod,FW\n",
        "alerts.csv": "native_id,created_at,severity,acknowledged_at,closed_at,case_ids,asset_ids\n"
                      f"A1,{PERIOD_START + 600},medium,{PERIOD_START + 1200},{PERIOD_START + 7200},C1,edge-02\n",
        "cases.csv": "native_id,opened_at,status,closed_at,owner,alert_ids,closure_reason\n"
                     f"C1,{PERIOD_START + 500},closed,{PERIOD_START + 7200},alice,A1,resolved\n",
        "investigation_steps.csv": "case_id,action_type,performed_at,sequence,analyst,note,evidence_ids\n",
        "escalations.csv": "alert_id,case_id,occurred_at,destination_role,trigger,outcome\n",
        "dispositions.csv": "alert_id,case_id,occurred_at,outcome,reason,approver_role\n",
    }
    _write_submission(directory, files)


def anomaly_cse(directory: Path) -> None:
    """Anomaly profile: closure times roughly uniform except for
    one extreme outlier (a 3-day closure on a single critical
    alert)."""
    files = {
        "assets.csv": "native_id,criticality,environment,controls\n"
                      "anom-01,critical,prod,AV\n",
        "alerts.csv": "native_id,created_at,severity,acknowledged_at,closed_at,case_ids,asset_ids\n"
                      f"A1,{PERIOD_START + 100},critical,{PERIOD_START + 600},{PERIOD_START + 3600},C1,anom-01\n"
                      f"A2,{PERIOD_START + 200},critical,{PERIOD_START + 700},{PERIOD_START + 3700},C2,anom-01\n"
                      f"A3,{PERIOD_START + 300},critical,{PERIOD_START + 800},{PERIOD_START + 3800},C3,anom-01\n"
                      f"A4,{PERIOD_START + 400},critical,{PERIOD_START + 900},{PERIOD_START + 3900},C4,anom-01\n"
                      f"A5,{PERIOD_START + 500},critical,{PERIOD_START + 1000},{PERIOD_START + 4000},C5,anom-01\n"
                      f"OUT,{PERIOD_START + 600},critical,{PERIOD_START + 1100},{PERIOD_START + 3 * 86400},C6,anom-01\n",
        "cases.csv": "native_id,opened_at,status,closed_at,owner,alert_ids,closure_reason\n"
                     f"C1,{PERIOD_START + 50},closed,{PERIOD_START + 3600},alice,A1,resolved\n"
                     f"C2,{PERIOD_START + 150},closed,{PERIOD_START + 3700},alice,A2,resolved\n"
                     f"C3,{PERIOD_START + 250},closed,{PERIOD_START + 3800},alice,A3,resolved\n"
                     f"C4,{PERIOD_START + 350},closed,{PERIOD_START + 3900},alice,A4,resolved\n"
                     f"C5,{PERIOD_START + 450},closed,{PERIOD_START + 4000},alice,A5,resolved\n"
                     f"C6,{PERIOD_START + 550},closed,{PERIOD_START + 3 * 86400},alice,OUT,long-running\n",
        "investigation_steps.csv": "case_id,action_type,performed_at,sequence,analyst,note,evidence_ids\n"
                                  f"C1,triage,{PERIOD_START + 200},1,alice,reviewed,EV-1\n"
                                  f"C2,triage,{PERIOD_START + 300},1,alice,reviewed,EV-2\n"
                                  f"C3,triage,{PERIOD_START + 400},1,alice,reviewed,EV-3\n"
                                  f"C4,triage,{PERIOD_START + 500},1,alice,reviewed,EV-4\n"
                                  f"C5,triage,{PERIOD_START + 600},1,alice,reviewed,EV-5\n"
                                  f"C6,triage,{PERIOD_START + 800},1,alice,started,EV-6\n"
                                  f"C6,deep-dive,{PERIOD_START + 7200},2,alice,investigating,EV-7\n",
        "escalations.csv": "alert_id,case_id,occurred_at,destination_role,trigger,outcome\n"
                           f"OUT,C6,{PERIOD_START + 1200},soc-l2,long-running,acknowledged\n",
        "dispositions.csv": "alert_id,case_id,occurred_at,outcome,reason,approver_role\n"
                           f"A1,C1,{PERIOD_START + 3500},true_positive,resolved,alice\n"
                           f"A2,C2,{PERIOD_START + 3600},true_positive,resolved,alice\n"
                           f"A3,C3,{PERIOD_START + 3700},true_positive,resolved,alice\n"
                           f"A4,C4,{PERIOD_START + 3800},true_positive,resolved,alice\n"
                           f"A5,C5,{PERIOD_START + 3900},true_positive,resolved,alice\n"
                           f"OUT,C6,{PERIOD_START + 3 * 86400},true_positive,confirmed,alice\n",
    }
    _write_submission(directory, files)


def peer_deviation_cse(directory: Path) -> None:
    """Peer-deviation profile: subject closes criticals in ~30s
    while peers typically close in ~30 minutes."""
    files = {
        "assets.csv": "native_id,criticality,environment,controls\n"
                      "peer-01,critical,prod,AV\n",
        "alerts.csv": "native_id,created_at,severity,acknowledged_at,closed_at,case_ids,asset_ids\n"
                      f"A1,{PERIOD_START + 100},critical,{PERIOD_START + 200},{PERIOD_START + 300},C1,peer-01\n"
                      f"A2,{PERIOD_START + 200},critical,{PERIOD_START + 300},{PERIOD_START + 400},C2,peer-01\n"
                      f"A3,{PERIOD_START + 300},critical,{PERIOD_START + 400},{PERIOD_START + 500},C3,peer-01\n",
        "cases.csv": "native_id,opened_at,status,closed_at,owner,alert_ids,closure_reason\n"
                     f"C1,{PERIOD_START + 50},closed,{PERIOD_START + 300},alice,A1,resolved\n"
                     f"C2,{PERIOD_START + 150},closed,{PERIOD_START + 400},alice,A2,resolved\n"
                     f"C3,{PERIOD_START + 250},closed,{PERIOD_START + 500},alice,A3,resolved\n",
        "investigation_steps.csv": "case_id,action_type,performed_at,sequence,analyst,note,evidence_ids\n"
                                  f"C1,triage,{PERIOD_START + 80},1,alice,ok,EV-1\n"
                                  f"C2,triage,{PERIOD_START + 180},1,alice,ok,EV-2\n"
                                  f"C3,triage,{PERIOD_START + 280},1,alice,ok,EV-3\n",
        "escalations.csv": "alert_id,case_id,occurred_at,destination_role,trigger,outcome\n"
                           f"A1,C1,{PERIOD_START + 150},soc-l2,severity critical,acknowledged\n"
                           f"A2,C2,{PERIOD_START + 250},soc-l2,severity critical,acknowledged\n"
                           f"A3,C3,{PERIOD_START + 350},soc-l2,severity critical,acknowledged\n",
        "dispositions.csv": "alert_id,case_id,occurred_at,outcome,reason,approver_role\n"
                           f"A1,C1,{PERIOD_START + 280},false_positive,ok,alice\n"
                           f"A2,C2,{PERIOD_START + 380},false_positive,ok,alice\n"
                           f"A3,C3,{PERIOD_START + 480},false_positive,ok,alice\n",
    }
    _write_submission(directory, files)


GROUND_TRUTH = {
    "CSE-HEALTHY": {
        "expected_signal_rules": [],
        "expected_dimensions_with_score": [],
        "notes": "all metrics healthy; no signals",
    },
    "CSE-EXEC": {
        "expected_signal_rules": [
            "execution_gap.fast_closure",
            "execution_gap.critical_without_escalation",
            "execution_gap.recurring_without_remediation",
            "execution_gap.potential_metric_gaming",
        ],
        "expected_dimensions_with_score": ["execution_gap", "peer_deviation"],
        "notes": "fast closures, no escalation on A3, recurring C4, gaming shape",
    },
    "CSE-NEG": {
        "expected_signal_rules": [
            "negative_space.missing_monitoring",
            "negative_space.missing_investigation",
            "negative_space.missing_disposition",
        ],
        "expected_dimensions_with_score": ["negative_space", "detection_gap"],
        "notes": "no escalations file → no escalation; missing monitoring/investigation/disposition",
    },
    "CSE-ANOM": {
        "expected_signal_rules": [
            "anomaly.investigation_duration.high",
        ],
        "expected_dimensions_with_score": ["anomaly"],
        "notes": "C6 takes 3 days — outlier",
    },
    "CSE-PEER": {
        "expected_signal_rules": [
            "peer_benchmark.escalation_rate.deviation",
            "peer_benchmark.alerts_per_critical_asset.deviation",
        ],
        "expected_dimensions_with_score": ["peer_deviation"],
        "notes": "30s median closure vs 30 min peer median (fires as peer_benchmark.escalation_rate + alerts_per_critical_asset in the demo's small cohort; closure_median_seconds is masked by CSE-HEALTHY's long-closure outlier in the MAD)",
    },
}


def build():
    root = Path(__file__).resolve().parents[1] / "docs" / "demo" / "submissions"
    builders = {
        "CSE-HEALTHY": healthy_cse,
        "CSE-EXEC": exec_gap_cse,
        "CSE-NEG": negative_space_cse,
        "CSE-ANOM": anomaly_cse,
        "CSE-PEER": peer_deviation_cse,
    }
    for cse_id, fn in builders.items():
        fn(root / cse_id)
    gt_path = root.parent / "ground-truth.json"
    gt_path.write_text(json.dumps(GROUND_TRUTH, indent=2), encoding="utf-8")
    print(f"Built {len(builders)} demo submissions under {root}")
    print(f"Ground truth at {gt_path}")


if __name__ == "__main__":
    build()

"""SAT-SA scalable synthetic dataset generator.

Deterministic by seed. Produces submission directories for any
number of CSEs with configurable alert volume and controlled
pathological scenarios.

The generator emits the same six CSV files the SAT-SA ingestion
pipeline consumes (alerts / cases / investigation_steps /
escalations / dispositions / assets). It goes through the same
ingestion path as real submissions, so the output is a real
end-to-end test of the system.
"""
from __future__ import annotations

import csv
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

PERIOD_START = 1735689600.0  # 2025-01-01T00:00:00Z
PERIOD_END = 1738281600.0    # 2025-02-01T00:00:00Z


@dataclass
class GenConfig:
    seed: int = 42
    num_cse: int = 5
    num_assets: int = 10
    num_alerts: int = 20
    num_cases: int = 5
    steps_per_case: int = 3
    escalation_rate: float = 0.4   # probability a closed alert has an escalation
    disposition_rate: float = 0.7
    fast_closure_rate: float = 0.2  # probability a critical alert closes in <300s
    missing_investigation_rate: float = 0.1
    no_remediation_rate: float = 0.2
    asset_critical_fraction: float = 0.4  # fraction of assets that are critical
    sector: str = "defence"
    environment: str = "on-prem"


@dataclass
class _CSE:
    name: str
    sector: str
    environment: str
    assets: list
    alerts: list
    cases: list
    steps: list
    escalations: list
    dispositions: list


def _rand(cfg: GenConfig) -> random.Random:
    return random.Random(cfg.seed)


def _gen_cse(cfg: GenConfig, idx: int) -> _CSE:
    rng = _rand(cfg)
    name = f"CSE-SYN-{idx:04d}"
    # Assets
    assets = []
    for a in range(cfg.num_assets):
        criticality = "critical" if rng.random() < cfg.asset_critical_fraction else "high"
        env = "prod" if rng.random() < 0.7 else "dev"
        assets.append({
            "native_id": f"asset-{idx:04d}-{a:03d}",
            "criticality": criticality,
            "environment": env,
            "controls": "AV;EDR" if criticality == "critical" else "AV",
        })
    # Cases
    cases = []
    for c in range(cfg.num_cases):
        opened = PERIOD_START + rng.uniform(0, 7 * 86400)
        cases.append({
            "native_id": f"case-{idx:04d}-{c:03d}",
            "opened_at": opened,
            "status": "closed" if rng.random() < 0.8 else "open",
            "closed_at": opened + rng.uniform(3600, 48 * 3600) if rng.random() < 0.8 else None,
            "owner": rng.choice(["alice", "bob", "carol"]),
            "alert_ids": [],
            "closure_reason": "resolved",
        })
    # Alerts
    alerts = []
    for i in range(cfg.num_alerts):
        asset = rng.choice(assets)
        if asset["criticality"] == "critical":
            severity = rng.choices(
                ["critical", "high", "medium", "low"],
                weights=[0.3, 0.4, 0.2, 0.1])[0]
        else:
            severity = rng.choices(
                ["critical", "high", "medium", "low"],
                weights=[0.05, 0.2, 0.5, 0.25])[0]
        created = PERIOD_START + rng.uniform(0, 28 * 86400)
        ack = created + rng.uniform(30, 600)
        if severity in ("critical", "high") and rng.random() < cfg.fast_closure_rate:
            close = ack + rng.uniform(30, 300)
        else:
            close = ack + rng.uniform(3600, 48 * 3600)
        case = rng.choice(cases)
        case["alert_ids"].append(f"alert-{idx:04d}-{i:04d}")
        alerts.append({
            "native_id": f"alert-{idx:04d}-{i:04d}",
            "created_at": created,
            "severity": severity,
            "ack_at": ack,
            "closed_at": close,
            "case_id": case["native_id"],
            "asset_id": asset["native_id"],
        })
    # Steps
    steps = []
    for c in cases:
        if rng.random() < cfg.missing_investigation_rate:
            continue  # no steps for this case
        for s in range(cfg.steps_per_case):
            steps.append({
                "case_id": c["native_id"],
                "action_type": rng.choice(["triage", "containment", "eradication", "recovery", "review"]),
                "performed_at": c["opened_at"] + (s + 1) * 1800,
                "sequence": s + 1,
                "analyst": c["owner"],
                "note": "auto-generated step",
                "evidence_ids": f"EV-{c['native_id']}-{s}",
            })
    # Escalations
    escalations = []
    for a in alerts:
        if a["severity"] in ("critical", "high") and rng.random() < cfg.escalation_rate:
            escalations.append({
                "alert_id": a["native_id"],
                "case_id": a["case_id"],
                "occurred_at": a["ack_at"] + 100,
                "destination": "soc-l2",
                "trigger": "severity " + a["severity"],
                "outcome": "acknowledged",
            })
    # Dispositions
    dispositions = []
    for a in alerts:
        if rng.random() < cfg.disposition_rate:
            cat = rng.choice(["true_positive", "false_positive", "benign"])
            dispositions.append({
                "alert_id": a["native_id"],
                "case_id": a["case_id"],
                "occurred_at": a["closed_at"] + 200,
                "outcome": cat,
                "reason": "auto",
                "approver": "soc-lead",
            })
    return _CSE(
        name=name, sector=cfg.sector, environment=cfg.environment,
        assets=assets, alerts=alerts, cases=cases, steps=steps,
        escalations=escalations, dispositions=dispositions,
    )


def _write_cse(cse: _CSE, outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    with open(outdir / "assets.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["native_id", "criticality", "environment", "controls"])
        w.writeheader()
        w.writerows(cse.assets)
    with open(outdir / "alerts.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "native_id", "created_at", "severity", "ack_at", "closed_at",
            "case_id", "asset_id",
        ])
        w.writeheader()
        w.writerows(cse.alerts)
    with open(outdir / "cases.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "native_id", "opened_at", "status", "closed_at", "owner",
            "alert_ids", "closure_reason",
        ])
        w.writeheader()
        for c in cse.cases:
            row = dict(c)
            row["alert_ids"] = ";".join(row["alert_ids"])
            w.writerow(row)
    with open(outdir / "investigation_steps.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "case_id", "action_type", "performed_at", "sequence",
            "analyst", "note", "evidence_ids",
        ])
        w.writeheader()
        w.writerows(cse.steps)
    with open(outdir / "escalations.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "alert_id", "case_id", "occurred_at",
            "destination", "trigger", "outcome",
        ])
        w.writeheader()
        w.writerows(cse.escalations)
    with open(outdir / "dispositions.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "alert_id", "case_id", "occurred_at",
            "outcome", "reason", "approver",
        ])
        w.writeheader()
        w.writerows(cse.dispositions)


def generate(cfg: GenConfig, outroot: Path) -> list[Path]:
    outroot.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in range(cfg.num_cse):
        cse = _gen_cse(cfg, i)
        d = outroot / cse.name
        _write_cse(cse, d)
        paths.append(d)
    return paths


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--num-cse", type=int, default=5)
    p.add_argument("--num-alerts", type=int, default=20)
    p.add_argument("--num-cases", type=int, default=5)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    cfg = GenConfig(seed=args.seed, num_cse=args.num_cse, num_alerts=args.num_alerts,
                   num_cases=args.num_cases)
    paths = generate(cfg, args.out)
    print(f"Generated {len(paths)} CSEs at {args.out}")

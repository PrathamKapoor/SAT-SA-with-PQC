"""The controlled workflow generator: reads ``policy.yaml``'s declared
scenarios and produces cases / investigation_steps / escalations /
dispositions on top of caller-supplied (source-derived) alerts and
assets.

Every record this module produces carries a ``"provenance"`` key
(see ``public_benchmarks.provenance.synthetic_workflow``) — these are
controlled validation fixtures, never a claim about real analyst
behavior. See this package's ``__init__.py`` docstring. The
``provenance`` key is intentionally NOT one of ``satsa.ingest.spec``'s
canonical CSV columns — ``serialize.py``'s CSV writers strip it before
writing, and ``serialize.provenance_manifest()`` extracts it into a
separate, auditable JSON sidecar instead, so the generated CSVs stay
byte-for-byte compatible with what ``satsa.ingest`` expects from any
other submission.

Design note: each scenario is a small, dedicated Python function
(``_gen_<scenario_id>``), not a generic declarative rule interpreter
over ``policy.yaml``. ``policy.yaml`` still carries every scenario's
parameters, description, and expected signal families — it is the
single source of truth for *what* each scenario claims to do — but
*how* each one is built stays in explicit, readable code, matching
this project's existing preference (``satsa/analysis/synth.py``) for
inspectable generator functions over a rule-interpretation layer that
would itself need trusting.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from public_benchmarks.provenance import synthetic_workflow
from satsa.analysis.workers.fast_closure import DEFAULT_FAST_CLOSURE_POLICY

POLICY_PATH = Path(__file__).resolve().parent / "policy.yaml"

# Any alert closed at or beyond this many seconds is safely above
# every FastClosureWorker per-severity threshold (critical/high/
# medium = 600/1800/3600s by default) regardless of the alert's own
# severity — used by every scenario that must NOT accidentally also
# trigger execution_gap.fast_closure.
_SAFE_SLOW_CLOSURE_SECONDS = DEFAULT_FAST_CLOSURE_POLICY.medium_max_seconds + 400


@dataclass
class WorkflowBundle:
    scenario_id: str
    source_dataset: str
    alerts_used: list = field(default_factory=list)   # the input alert dicts actually referenced
    extra_assets: list = field(default_factory=list)   # new assets this scenario invents (e.g. silent_critical_asset)
    cases: list = field(default_factory=list)
    investigation_steps: list = field(default_factory=list)
    escalations: list = field(default_factory=list)
    dispositions: list = field(default_factory=list)
    omit_categories: frozenset = field(default_factory=frozenset)

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "source_dataset": self.source_dataset,
            "alerts_used": [a["native_id"] for a in self.alerts_used],
            "extra_assets": [a["native_id"] for a in self.extra_assets],
            "cases": len(self.cases),
            "investigation_steps": len(self.investigation_steps),
            "escalations": len(self.escalations),
            "dispositions": len(self.dispositions),
            "omit_categories": sorted(self.omit_categories),
        }


def load_policy(path: Optional[Path] = None) -> dict:
    path = Path(path) if path else POLICY_PATH
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def list_scenarios(policy: Optional[dict] = None) -> list:
    policy = policy or load_policy()
    return [s["scenario_id"] for s in policy["scenarios"]]


def get_scenario(scenario_id: str, policy: Optional[dict] = None) -> dict:
    policy = policy or load_policy()
    for s in policy["scenarios"]:
        if s["scenario_id"] == scenario_id:
            return s
    raise KeyError(f"unknown scenario_id: {scenario_id!r}; known: {list_scenarios(policy)}")


# ---------------------------------------------------------------------------
# shared helpers — every _mk_* call is bound to one (scenario_id,
# source_dataset, policy_version) context via _Ctx, so every record it
# produces carries the same provenance tag without repeating it at
# every call site.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Ctx:
    scenario_id: str
    source_dataset: str
    policy_version: str

    def tag(self) -> dict:
        return synthetic_workflow(
            self.source_dataset, scenario_id=self.scenario_id,
            policy_version=self.policy_version).to_dict()


def _case(ctx: _Ctx, index: int, *, opened_at: float,
         closed_at: Optional[float], alert_ids: list,
         owner: str = "benchmark-analyst") -> dict:
    return {
        "native_id": f"{ctx.scenario_id}-case-{index}",
        "opened_at": opened_at,
        "status": "closed" if closed_at is not None else "open",
        "closed_at": closed_at,
        "owner": owner,
        "alert_ids": list(alert_ids),
        "closure_reason": "benchmark-generated" if closed_at is not None else "",
        "provenance": ctx.tag(),
    }


def _step(ctx: _Ctx, case_id: str, index: int, *, action_type: str,
          performed_at: float, note: str, analyst: str = "benchmark-analyst") -> dict:
    return {
        "case_id": case_id, "action_type": action_type,
        "performed_at": performed_at, "sequence": index,
        "analyst": analyst, "note": note, "evidence_ids": [],
        "provenance": ctx.tag(),
    }


def _escalation(ctx: _Ctx, alert_id: str, case_id: str, *, occurred_at: float,
                destination_role: str = "soc-l2", trigger: str = "severity") -> dict:
    return {
        "alert_id": alert_id, "case_id": case_id, "occurred_at": occurred_at,
        "destination_role": destination_role, "trigger": trigger,
        "outcome": "acknowledged",
        "provenance": ctx.tag(),
    }


def _disposition(ctx: _Ctx, alert_id: str, case_id: str, *, occurred_at: float,
                 outcome: str = "true_positive", reason: str = "benchmark-generated",
                 approver_role: str = "soc-lead") -> dict:
    return {
        "alert_id": alert_id, "case_id": case_id, "occurred_at": occurred_at,
        "outcome": outcome, "reason": reason, "approver_role": approver_role,
        "provenance": ctx.tag(),
    }


def _asset(ctx: _Ctx, native_id: str, *, criticality: str) -> dict:
    return {"native_id": native_id, "criticality": criticality, "provenance": ctx.tag()}


# ---------------------------------------------------------------------------
# scenario functions
# ---------------------------------------------------------------------------

def _gen_healthy_control(alerts, assets, *, params, ctx: _Ctx):
    bundle = WorkflowBundle(scenario_id=ctx.scenario_id, source_dataset=ctx.source_dataset)
    for i, a in enumerate(alerts):
        ack_at = a["created_at"] + 60
        closed_at = ack_at + max(params["close_after_seconds_min"],
                                  min(params["close_after_seconds_max"], 7200))
        case_native_id = f"{ctx.scenario_id}-case-{i}"
        bundle.alerts_used.append(dict(
            a, acknowledged_at=ack_at, closed_at=closed_at, case_ids=[case_native_id]))
        case = _case(ctx, i, opened_at=ack_at, closed_at=closed_at, alert_ids=[a["native_id"]])
        bundle.cases.append(case)
        t = ack_at
        for j, step_type in enumerate(params["investigation_steps"], start=1):
            t += 300
            bundle.investigation_steps.append(_step(
                ctx, case["native_id"], j, action_type=step_type,
                performed_at=t, note=f"{step_type} completed per runbook"))
        if a["severity"] in params.get("escalate_severities", []):
            bundle.escalations.append(_escalation(
                ctx, a["native_id"], case["native_id"], occurred_at=ack_at + 120))
        bundle.dispositions.append(_disposition(
            ctx, a["native_id"], case["native_id"], occurred_at=closed_at))
    return bundle


def _gen_fast_closure(alerts, assets, *, params, ctx: _Ctx):
    bundle = WorkflowBundle(scenario_id=ctx.scenario_id, source_dataset=ctx.source_dataset)
    critical_alerts = [a for a in alerts if a["severity"] == "critical"]
    for i, a in enumerate(critical_alerts):
        ack_at = a["created_at"] + 5
        closed_at = ack_at + max(params["close_after_seconds_min"],
                                  min(params["close_after_seconds_max"], 90))
        case_native_id = f"{ctx.scenario_id}-case-{i}"
        bundle.alerts_used.append(dict(
            a, acknowledged_at=ack_at, closed_at=closed_at, case_ids=[case_native_id]))
        case = _case(ctx, i, opened_at=ack_at, closed_at=closed_at, alert_ids=[a["native_id"]])
        bundle.cases.append(case)
        for j, step_type in enumerate(params.get("investigation_steps", []), start=1):
            bundle.investigation_steps.append(_step(
                ctx, case["native_id"], j, action_type=step_type,
                performed_at=ack_at + 10, note="quick check"))
        bundle.dispositions.append(_disposition(
            ctx, a["native_id"], case["native_id"], occurred_at=closed_at))
    return bundle


def _gen_no_escalation(alerts, assets, *, params, ctx: _Ctx):
    bundle = WorkflowBundle(scenario_id=ctx.scenario_id, source_dataset=ctx.source_dataset)
    critical_alerts = [a for a in alerts if a["severity"] == "critical"]
    for i, a in enumerate(critical_alerts):
        ack_at = a["created_at"] + 60
        closed_at = ack_at + _SAFE_SLOW_CLOSURE_SECONDS
        case_native_id = f"{ctx.scenario_id}-case-{i}"
        bundle.alerts_used.append(dict(
            a, acknowledged_at=ack_at, closed_at=closed_at, case_ids=[case_native_id]))
        case = _case(ctx, i, opened_at=ack_at, closed_at=closed_at, alert_ids=[a["native_id"]])
        bundle.cases.append(case)
        for j, step_type in enumerate(params.get("investigation_steps", []), start=1):
            bundle.investigation_steps.append(_step(
                ctx, case["native_id"], j, action_type=step_type,
                performed_at=ack_at + 300, note=f"{step_type} completed"))
        bundle.dispositions.append(_disposition(
            ctx, a["native_id"], case["native_id"], occurred_at=closed_at))
        # deliberately no escalation record
    return bundle


def _gen_ack_no_investigation(alerts, assets, *, params, ctx: _Ctx):
    bundle = WorkflowBundle(scenario_id=ctx.scenario_id, source_dataset=ctx.source_dataset)
    eligible = [a for a in alerts if a["severity"] in ("critical", "high", "medium")]
    for i, a in enumerate(eligible):
        ack_at = a["created_at"] + 60
        closed_at = ack_at + max(params["close_after_seconds_min"],
                                  min(params["close_after_seconds_max"], 3000))
        case_native_id = f"{ctx.scenario_id}-case-{i}"
        bundle.alerts_used.append(dict(
            a, acknowledged_at=ack_at, closed_at=closed_at, case_ids=[case_native_id]))
        case = _case(ctx, i, opened_at=ack_at, closed_at=closed_at, alert_ids=[a["native_id"]])
        bundle.cases.append(case)
        # exactly one shallow step -- below min_steps_per_case=2, but
        # not zero, so negative_space.missing_investigation stays quiet.
        bundle.investigation_steps.append(_step(
            ctx, case["native_id"], 1, action_type="triage",
            performed_at=ack_at + 120, note="closed, no further action"))
        bundle.dispositions.append(_disposition(
            ctx, a["native_id"], case["native_id"], occurred_at=closed_at))
    return bundle


def _gen_missing_investigation(alerts, assets, *, params, ctx: _Ctx):
    bundle = WorkflowBundle(scenario_id=ctx.scenario_id, source_dataset=ctx.source_dataset)
    for i, a in enumerate(alerts):
        closed_at = a["created_at"] + max(params["close_after_seconds_min"],
                                           min(params["close_after_seconds_max"], 5000))
        # deliberately no acknowledged_at -- keeps ack_without_investigation quiet
        bundle.alerts_used.append(dict(a, acknowledged_at=None, closed_at=closed_at))
        case = _case(ctx, i, opened_at=a["created_at"] + 30, closed_at=closed_at,
                    alert_ids=[a["native_id"]])
        bundle.cases.append(case)
        # deliberately zero investigation_steps
        if a["severity"] in params.get("escalate_severities", []):
            bundle.escalations.append(_escalation(
                ctx, a["native_id"], case["native_id"], occurred_at=closed_at - 100))
        bundle.dispositions.append(_disposition(
            ctx, a["native_id"], case["native_id"], occurred_at=closed_at))
    return bundle


def _gen_missing_escalation_file(alerts, assets, *, params, ctx: _Ctx):
    bundle = WorkflowBundle(scenario_id=ctx.scenario_id, source_dataset=ctx.source_dataset)
    critical_alerts = [a for a in alerts if a["severity"] == "critical"]
    for i, a in enumerate(critical_alerts):
        ack_at = a["created_at"] + 60
        closed_at = ack_at + max(params["close_after_seconds_min"],
                                  min(params["close_after_seconds_max"], 3000))
        case_native_id = f"{ctx.scenario_id}-case-{i}"
        bundle.alerts_used.append(dict(
            a, acknowledged_at=ack_at, closed_at=closed_at, case_ids=[case_native_id]))
        case = _case(ctx, i, opened_at=ack_at, closed_at=closed_at, alert_ids=[a["native_id"]])
        bundle.cases.append(case)
        for j, step_type in enumerate(params.get("investigation_steps", []), start=1):
            bundle.investigation_steps.append(_step(
                ctx, case["native_id"], j, action_type=step_type,
                performed_at=ack_at + 200, note=f"{step_type} done"))
        bundle.dispositions.append(_disposition(
            ctx, a["native_id"], case["native_id"], occurred_at=closed_at))
    if params.get("omit_escalations_category"):
        bundle.omit_categories = frozenset({"escalations"})
    return bundle


def _gen_silent_critical_asset(alerts, assets, *, params, ctx: _Ctx):
    bundle = WorkflowBundle(scenario_id=ctx.scenario_id, source_dataset=ctx.source_dataset)
    bundle.alerts_used = list(alerts)  # untouched -- this scenario only adds assets
    count = params.get("silent_asset_count", 3)
    criticality = params.get("silent_asset_criticality", "critical")
    existing_ids = {a["native_id"] for a in assets}
    i = 0
    added = 0
    while added < count:
        candidate = f"{ctx.scenario_id}-silent-asset-{i}"
        i += 1
        if candidate in existing_ids:
            continue
        bundle.extra_assets.append(_asset(ctx, candidate, criticality=criticality))
        added += 1
    return bundle


def _gen_low_activity(alerts, assets, *, params, ctx: _Ctx):
    bundle = WorkflowBundle(scenario_id=ctx.scenario_id, source_dataset=ctx.source_dataset)
    max_count = params.get("max_alert_count", 2)
    selected = alerts[:max_count]
    for i, a in enumerate(selected):
        ack_at = a["created_at"] + 60
        closed_at = ack_at + max(params["close_after_seconds_min"],
                                  min(params["close_after_seconds_max"], 5000))
        case_native_id = f"{ctx.scenario_id}-case-{i}"
        bundle.alerts_used.append(dict(
            a, acknowledged_at=ack_at, closed_at=closed_at, case_ids=[case_native_id]))
        case = _case(ctx, i, opened_at=ack_at, closed_at=closed_at, alert_ids=[a["native_id"]])
        bundle.cases.append(case)
        for j, step_type in enumerate(params.get("investigation_steps", []), start=1):
            bundle.investigation_steps.append(_step(
                ctx, case["native_id"], j, action_type=step_type,
                performed_at=ack_at + 200, note=f"{step_type} done"))
        bundle.dispositions.append(_disposition(
            ctx, a["native_id"], case["native_id"], occurred_at=closed_at))
    return bundle


def _gen_template_investigation(alerts, assets, *, params, ctx: _Ctx):
    bundle = WorkflowBundle(scenario_id=ctx.scenario_id, source_dataset=ctx.source_dataset)
    min_steps = params.get("min_steps_total", 6)
    action_type = params.get("template_action_type", "triage")
    note = params.get("template_note", "reviewed, no action needed")
    analyst = params.get("template_analyst", "shared-queue-analyst")
    source = list(alerts) or []
    if not source:
        return bundle
    case_index = 0
    while case_index < min_steps:
        a = source[case_index % len(source)]
        ack_at = a["created_at"] + 60
        closed_at = ack_at + max(params["close_after_seconds_min"],
                                  min(params["close_after_seconds_max"], 3000))
        # every repeated pass over `source` needs a distinct alert
        # native_id so satsa.ingest doesn't reject it as a duplicate.
        alert_id = f"{a['native_id']}-{case_index}"
        bundle.alerts_used.append(dict(
            a, native_id=alert_id, acknowledged_at=ack_at, closed_at=closed_at))
        case = _case(ctx, case_index, opened_at=ack_at, closed_at=closed_at,
                    alert_ids=[alert_id])
        bundle.cases.append(case)
        bundle.investigation_steps.append(_step(
            ctx, case["native_id"], 1, action_type=action_type,
            performed_at=ack_at + 100, note=note, analyst=analyst))
        bundle.dispositions.append(_disposition(
            ctx, alert_id, case["native_id"], occurred_at=closed_at))
        case_index += 1
    return bundle


def _gen_recurring_no_remediation(alerts, assets, *, params, ctx: _Ctx):
    bundle = WorkflowBundle(scenario_id=ctx.scenario_id, source_dataset=ctx.source_dataset)
    min_count = params.get("recurrence_min_count", 4)
    source = list(alerts) or []
    if not source:
        return bundle
    base = source[0]
    case_native_id = f"{ctx.scenario_id}-case-0"
    linked_alert_ids = []
    for k in range(min_count):
        a = source[k % len(source)]
        alert_id = f"{ctx.scenario_id}-recur-alert-{k}"
        created_at = base["created_at"] + k * 600
        bundle.alerts_used.append(dict(
            a, native_id=alert_id, created_at=created_at,
            acknowledged_at=created_at + 60,
            closed_at=created_at + _SAFE_SLOW_CLOSURE_SECONDS,
            case_ids=[case_native_id]))
        linked_alert_ids.append(alert_id)
    last_closed = bundle.alerts_used[-1]["closed_at"]
    case = _case(ctx, 0, opened_at=base["created_at"], closed_at=last_closed,
                alert_ids=linked_alert_ids)
    bundle.cases.append(case)
    for alert_id, a2 in zip(linked_alert_ids, bundle.alerts_used):
        bundle.dispositions.append(_disposition(
            ctx, alert_id, case["native_id"], occurred_at=a2["closed_at"],
            outcome=params.get("disposition_outcome", "benign")))
    # deliberately zero remediation (not an ingestible CSV field at all)
    return bundle


def _gen_peer_outlier(alerts, assets, *, params, ctx: _Ctx):
    """The *subject* entity's bundle only. See
    ``generate_peer_entity_workflow`` for building each peer's bundle
    from the same scenario's peer_* params."""
    bundle = WorkflowBundle(scenario_id=ctx.scenario_id, source_dataset=ctx.source_dataset)
    eligible = [a for a in alerts if a["severity"] in ("critical", "high")]
    for i, a in enumerate(eligible):
        ack_at = a["created_at"] + 5
        closed_at = ack_at + max(params["close_after_seconds_min"],
                                  min(params["close_after_seconds_max"], 60))
        case_native_id = f"{ctx.scenario_id}-case-{i}"
        bundle.alerts_used.append(dict(
            a, acknowledged_at=ack_at, closed_at=closed_at, case_ids=[case_native_id]))
        case = _case(ctx, i, opened_at=ack_at, closed_at=closed_at, alert_ids=[a["native_id"]])
        bundle.cases.append(case)
        for j, step_type in enumerate(params.get("investigation_steps", []), start=1):
            bundle.investigation_steps.append(_step(
                ctx, case["native_id"], j, action_type=step_type,
                performed_at=ack_at + 10, note=f"{step_type} done"))
        if a["severity"] in params.get("escalate_severities", []):
            bundle.escalations.append(_escalation(
                ctx, a["native_id"], case["native_id"], occurred_at=ack_at + 20))
        bundle.dispositions.append(_disposition(
            ctx, a["native_id"], case["native_id"], occurred_at=closed_at))
    return bundle


def generate_peer_entity_workflow(alerts, assets, *, source_dataset,
                                  policy: Optional[dict] = None,
                                  peer_label: str = "peer") -> WorkflowBundle:
    """Build one peer entity's bundle for the ``peer_outlier`` scenario,
    using its ``peer_close_after_seconds_min/max`` params — a normal,
    healthy-paced closure, matching ``healthy_control``'s behaviour but
    scoped under a distinct scenario_id so peer records are never
    confused with the subject entity's own records."""
    policy = policy or load_policy()
    scenario = get_scenario("peer_outlier", policy)
    params = scenario["params"]
    scenario_id = f"peer_outlier-{peer_label}"
    ctx = _Ctx(scenario_id, source_dataset, policy["policy_version"])
    bundle = WorkflowBundle(scenario_id=scenario_id, source_dataset=source_dataset)
    eligible = [a for a in alerts if a["severity"] in ("critical", "high")]
    for i, a in enumerate(eligible):
        ack_at = a["created_at"] + 60
        closed_at = ack_at + max(params["peer_close_after_seconds_min"],
                                  min(params["peer_close_after_seconds_max"], 10800))
        case_native_id = f"{ctx.scenario_id}-case-{i}"
        bundle.alerts_used.append(dict(
            a, acknowledged_at=ack_at, closed_at=closed_at, case_ids=[case_native_id]))
        case = _case(ctx, i, opened_at=ack_at, closed_at=closed_at, alert_ids=[a["native_id"]])
        bundle.cases.append(case)
        for j, step_type in enumerate(params.get("investigation_steps", []), start=1):
            bundle.investigation_steps.append(_step(
                ctx, case["native_id"], j, action_type=step_type,
                performed_at=ack_at + 300, note=f"{step_type} completed per runbook"))
        if a["severity"] in params.get("escalate_severities", []):
            bundle.escalations.append(_escalation(
                ctx, a["native_id"], case["native_id"], occurred_at=ack_at + 120))
        bundle.dispositions.append(_disposition(
            ctx, a["native_id"], case["native_id"], occurred_at=closed_at))
    return bundle


def _gen_multi_signal(alerts, assets, *, params, ctx: _Ctx):
    """Deliberately triggers TWO execution_gap rule families on the
    SAME alert/case: fast_closure (closed under threshold) and
    critical_without_escalation (no escalation record) — the intended
    target for satsa.analysis.correlation's cross-family
    corroboration."""
    bundle = WorkflowBundle(scenario_id=ctx.scenario_id, source_dataset=ctx.source_dataset)
    critical_alerts = [a for a in alerts if a["severity"] == "critical"]
    for i, a in enumerate(critical_alerts):
        ack_at = a["created_at"] + 5
        closed_at = ack_at + max(params["close_after_seconds_min"],
                                  min(params["close_after_seconds_max"], 90))
        case_native_id = f"{ctx.scenario_id}-case-{i}"
        bundle.alerts_used.append(dict(
            a, acknowledged_at=ack_at, closed_at=closed_at, case_ids=[case_native_id]))
        case = _case(ctx, i, opened_at=ack_at, closed_at=closed_at, alert_ids=[a["native_id"]])
        bundle.cases.append(case)
        for j, step_type in enumerate(params.get("investigation_steps", []), start=1):
            bundle.investigation_steps.append(_step(
                ctx, case["native_id"], j, action_type=step_type,
                performed_at=ack_at + 10, note="quick check"))
        bundle.dispositions.append(_disposition(
            ctx, a["native_id"], case["native_id"], occurred_at=closed_at))
        # deliberately no escalation record
    return bundle


_SCENARIO_FUNCS = {
    "healthy_control": _gen_healthy_control,
    "fast_closure": _gen_fast_closure,
    "no_escalation": _gen_no_escalation,
    "ack_no_investigation": _gen_ack_no_investigation,
    "missing_investigation": _gen_missing_investigation,
    "missing_escalation_file": _gen_missing_escalation_file,
    "silent_critical_asset": _gen_silent_critical_asset,
    "low_activity": _gen_low_activity,
    "template_investigation": _gen_template_investigation,
    "recurring_no_remediation": _gen_recurring_no_remediation,
    "peer_outlier": _gen_peer_outlier,
    "multi_signal": _gen_multi_signal,
}


def generate_workflow(alerts: list, assets: list, *, scenario_id: str,
                      source_dataset: str, policy: Optional[dict] = None) -> WorkflowBundle:
    """Generate a scenario's workflow records on top of ``alerts``
    (already source-derived, e.g. from
    ``public_benchmarks.cicids2017.ingest_adapter``) and ``assets``.

    Raises ``KeyError`` for an unknown ``scenario_id`` (via
    ``get_scenario``) — never silently falls back to a default
    scenario.
    """
    policy = policy or load_policy()
    scenario = get_scenario(scenario_id, policy)
    params = scenario["params"]
    fn = _SCENARIO_FUNCS[scenario_id]
    ctx = _Ctx(scenario_id, source_dataset, policy["policy_version"])
    return fn(alerts, assets, params=params, ctx=ctx)

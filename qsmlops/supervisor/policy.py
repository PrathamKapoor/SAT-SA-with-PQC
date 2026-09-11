"""Supervisor Policy Engine: declarative, data-driven governance.

Replaces hardcoded supervisor thresholds with an ordered rule set loaded from
JSON or YAML. Each rule maps observable *facts* (security score, signature
validity, aggregate risk, drift status, agent recommendations, ...) to a
Decision. Rules are evaluated in priority order; the first firing rule wins.

Deployment gates are rules whose action is BLOCK_DEPLOYMENT: they hard-stop
promotion regardless of any other signal (except learning-store escalation).

Example policy document::

    rules:
      - name: block_untrusted_signatures
        priority: 100
        description: >
          Block deployment when security posture degrades AND the passport
          signature fails verification.
        when:
          all:
            - {field: security_score, op: lt, value: 90}
            - {field: signature_invalid, op: eq, value: true}
        action: BLOCK_DEPLOYMENT

      - name: retrain_on_critical_drift
        priority: 60
        when:
          any:
            - {field: max_drift_severity, op: gte, value: CRITICAL}
            - {field: performance_risk, op: gte, value: 20}
        action: RETRAIN

Operators: lt lte gt gte eq ne in not_in contains exists truthy.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

SEVERITY_ORDER = {"NONE": -1, "LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

OPERATORS = {}


def _op(name):
    def deco(fn):
        OPERATORS[name] = fn
        return fn

    return deco


@_op("lt")
def _lt(a, b): return a < b


@_op("lte")
def _lte(a, b): return a <= b


@_op("gt")
def _gt(a, b): return a > b


@_op("gte")
def _gte(a, b): return a >= b


@_op("eq")
def _eq(a, b): return a == b


@_op("ne")
def _ne(a, b): return a != b


@_op("in")
def _in(a, b): return a in b


@_op("not_in")
def _not_in(a, b): return a not in b


@_op("contains")
def _contains(a, b): return b in a if hasattr(a, "__contains__") else False


@_op("exists")
def _exists(a, _b=None): return a is not None


@_op("truthy")
def _truthy(a, _b=None): return bool(a)


class PolicyError(Exception):
    pass


@dataclass
class Condition:
    field: str
    op: str
    value: object = None

    @classmethod
    def from_dict(cls, d: dict) -> "Condition":
        try:
            return cls(field=d["field"], op=d.get("op", "eq"), value=d.get("value"))
        except KeyError as exc:
            raise PolicyError(f"condition missing required key {exc}") from exc

    def matches(self, facts: dict) -> bool:
        fn = OPERATORS.get(self.op)
        if fn is None:
            raise PolicyError(f"unknown operator {self.op!r}")
        actual = facts.get(self.field)
        try:
            return bool(fn(actual, self.value))
        except TypeError:
            # incomparable types (e.g. None < 90) simply do not match
            return False


@dataclass
class Rule:
    name: str
    action: str
    priority: int = 50
    description: str = ""
    all_of: list[Condition] = field(default_factory=list)
    any_of: list[Condition] = field(default_factory=list)
    none_of: list[Condition] = field(default_factory=list)
    enabled: bool = True
    gate: bool = False  # True -> deployment gate (blocks promotion)

    @classmethod
    def from_dict(cls, d: dict) -> "Rule":
        if "action" not in d:
            raise PolicyError(f"rule {d.get('name', '?')!r} missing 'action'")
        when = d.get("when") or {}
        if isinstance(when, list):  # bare list == all-of semantics
            when = {"all": when}
        all_of = [Condition.from_dict(c) for c in when.get("all", [])]
        any_of = [Condition.from_dict(c) for c in when.get("any", [])]
        none_of = [Condition.from_dict(c) for c in when.get("none", [])]
        if not (all_of or any_of or none_of):
            raise PolicyError(f"rule {d['name']!r} has no conditions under 'when'")
        return cls(
            name=d.get("name", f"rule-{d['action'].lower()}"),
            action=str(d["action"]).upper(),
            priority=int(d.get("priority", 50)),
            description=d.get("description", ""),
            all_of=all_of,
            any_of=any_of,
            none_of=none_of,
            enabled=bool(d.get("enabled", True)),
            gate=bool(d.get("gate", str(d["action"]).upper() == "BLOCK_DEPLOYMENT")),
        )

    def matches(self, facts: dict) -> tuple[bool, list[str], list[str]]:
        """Returns (matched, satisfied_condition_summaries, unsatisfied_summaries)."""
        ok, sat, unsat = True, [], []
        for c in self.all_of + self.any_of + self.none_of:
            summary = f"{c.field} {c.op} {c.value!r}"
            try:
                m = c.matches(facts)
            except PolicyError:
                raise
            except Exception:
                m = False
            if m:
                sat.append(summary)
            else:
                unsat.append(summary)
        for c in self.all_of:
            if not c.matches(facts):
                ok = False
        if self.any_of and not any(c.matches(facts) for c in self.any_of):
            ok = False
        for c in self.none_of:
            if c.matches(facts):
                ok = False
        return ok, sat, unsat


@dataclass
class PolicyDecision:
    rule_name: str
    action: str
    priority: int
    matched_conditions: list[str]
    unmatched_conditions: list[str]
    description: str = ""
    gate: bool = False

    def to_dict(self) -> dict:
        return {
            "rule_name": self.rule_name,
            "action": self.action,
            "priority": self.priority,
            "matched_conditions": self.matched_conditions,
            "unmatched_conditions": self.unmatched_conditions,
            "description": self.description,
            "gate": self.gate,
        }


class PolicyEngine:
    """Ordered evaluation of declarative rules over a flat fact dictionary."""

    def __init__(self, rules: list[Rule] | None = None) -> None:
        self.rules: list[Rule] = sorted(rules or [], key=lambda r: -r.priority)

    # ---------------- construction ----------------
    @classmethod
    def from_document(cls, doc: dict) -> "PolicyEngine":
        raw_rules = doc.get("rules", [])
        rules = [Rule.from_dict(r) for r in raw_rules]
        engine = cls(rules)
        defaults = doc.get("thresholds") or {}
        engine.thresholds = {
            "quarantine_risk": float(defaults.get("quarantine_risk", 40.0)),
            "block_risk": float(defaults.get("block_risk", 55.0)),
            "escalate_risk": float(defaults.get("escalate_risk", 70.0)),
            "max_auto_recoveries": int(defaults.get("max_auto_recoveries", 2)),
            "min_security_score": float(defaults.get("min_security_score", 90.0)),
        }
        return engine

    @classmethod
    def from_file(cls, path: str | Path) -> "PolicyEngine":
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        if p.suffix.lower() in (".yaml", ".yml"):
            import yaml

            doc = yaml.safe_load(text)
        else:
            doc = json.loads(text)
        return cls.from_document(doc or {})

    def add_rule(self, rule: Rule) -> None:
        self.rules.append(rule)
        self.rules.sort(key=lambda r: -r.priority)

    # ---------------- evaluation ----------------
    def evaluate(self, facts: dict) -> list[PolicyDecision]:
        decisions: list[PolicyDecision] = []
        for rule in self.rules:
            if not rule.enabled:
                continue
            matched, sat, unsat = rule.matches(facts)
            if matched:
                decisions.append(
                    PolicyDecision(
                        rule_name=rule.name,
                        action=rule.action,
                        priority=rule.priority,
                        matched_conditions=sat,
                        unmatched_conditions=unsat,
                        description=rule.description,
                        gate=rule.gate,
                    )
                )
        return decisions

    def first_decision(self, facts: dict) -> PolicyDecision | None:
        ds = self.evaluate(facts)
        return ds[0] if ds else None

    def deployment_blocked(self, facts: dict) -> PolicyDecision | None:
        for d in self.evaluate(facts):
            if d.gate and d.action == "BLOCK_DEPLOYMENT":
                return d
        return None

    def to_dict(self) -> dict:
        return {
            "rules": [
                {
                    "name": r.name,
                    "action": r.action,
                    "priority": r.priority,
                    "description": r.description,
                    "enabled": r.enabled,
                    "gate": r.gate,
                    "when": {
                        **({"all": [c.__dict__ for c in r.all_of]} if r.all_of else {}),
                        **({"any": [c.__dict__ for c in r.any_of]} if r.any_of else {}),
                        **({"none": [c.__dict__ for c in r.none_of]} if r.none_of else {}),
                    },
                }
                for r in self.rules
            ],
            "thresholds": getattr(self, "thresholds", {}),
        }


# ----------------------------------------------------------------------
# Fact extraction: turns observations + context into the flat fact dict the
# policy language evaluates.
# ----------------------------------------------------------------------

def build_facts(
    observations,
    risk_score: float,
    per_agent_risk: dict[str, float],
    version_record: dict | None = None,
    scores: dict | None = None,
    drift_summary: dict | None = None,
    trust: dict | None = None,
) -> dict:
    recs = [obs.recommendation for obs in observations]
    findings_flat = [
        {"agent": obs.agent, **f.to_dict()}
        for obs in observations
        for f in obs.findings
    ]
    failed = [f for f in findings_flat if not f["passed"]]
    sig_findings = [
        f for f in findings_flat if f["name"] in ("passport_signature_valid", "passport_signed")
    ]
    signature_invalid = any(not f["passed"] for f in sig_findings)
    max_sev = "NONE"
    for f in failed:
        if SEVERITY_ORDER.get(f["severity"], -1) > SEVERITY_ORDER.get(max_sev, -1):
            max_sev = f["severity"]
    drift = drift_summary or {}
    # Drift findings are handled by their own dedicated rules (e.g.
    # rollback_on_critical_drift); they must not trigger hard quarantine.
    critical_non_drift_present = any(
        f["severity"] == "CRITICAL"
        and not f["passed"]
        and not str(f.get("name", "")).startswith("drift_")
        for f in findings_flat
    )
    facts = {
        "risk_score": round(risk_score, 3),
        "signature_invalid": signature_invalid,
        "critical_finding_present": critical_non_drift_present,
        "failed_finding_count": len(failed),
        "finding_count": len(findings_flat),
        "max_failed_severity": max_sev,
        "recommendation_block_deployment": "BLOCK_DEPLOYMENT" in recs,
        "recommendation_quarantine": "QUARANTINE" in recs,
        "recommendation_rotate_keys": "ROTATE_KEYS" in recs,
        "recommendation_retrain": "RETRAIN" in recs,
        "recommendation_rollback": "ROLLBACK" in recs,
        "recommendation_escalate": "ESCALATE" in recs,
        "distinct_recommendations": len(set(recs)),
        "state": (version_record or {}).get("state", ""),
        "model_state_deployed": (version_record or {}).get("state") == "DEPLOYED",
        **{f"{k}_risk": v for k, v in per_agent_risk.items()},
        **(scores or {}),
    }
    # Phase 5: expose the explainable trust evaluation to the policy layer so
    # rules can distinguish high-trust, low-trust and cryptographically
    # invalid models. Never used to bypass hard security failures.
    if trust:
        facts.update(
            {
                "trust_score": trust.get("trust_score"),
                "trust_decision": trust.get("decision"),
                "trust_promotion_eligible": bool(trust.get("promotion_eligible")),
                "trust_blocking_conditions": len(trust.get("blocking_conditions", [])),
            }
        )
    if drift:
        facts["drift_detected"] = bool(drift.get("drift_count"))
        facts["max_drift_severity"] = drift.get("max_severity", "NONE")
        facts["drift_count"] = drift.get("drift_count", 0)
    else:
        facts["drift_detected"] = False
        facts["max_drift_severity"] = "NONE"
        facts["drift_count"] = 0
    return facts


DEFAULT_POLICY_DOCUMENT: dict = {
    "rules": [
        {
            "name": "block_broken_trust_chain",
            "priority": 200,
            "gate": True,
            "description": "Invalid passport signature plus degraded security score blocks deployment.",
            "when": {
                "all": [
                    {"field": "security_score", "op": "lt", "value": 90},
                    {"field": "signature_invalid", "op": "eq", "value": True},
                ]
            },
            "action": "BLOCK_DEPLOYMENT",
        },
        {
            "name": "quarantine_critical_findings",
            "priority": 180,
            "description": "Any unresolved critical finding quarantines the version.",
            "when": {"all": [{"field": "critical_finding_present", "op": "eq", "value": True}]},
            "action": "QUARANTINE",
        },
        {
            "name": "rollback_on_critical_drift",
            "priority": 120,
            "description": "Critical-severity drift on an active deployment triggers rollback.",
            "when": {
                "all": [
                    {"field": "max_drift_severity", "op": "eq", "value": "CRITICAL"},
                    {"field": "model_state_deployed", "op": "eq", "value": True},
                ]
            },
            "action": "ROLLBACK",
        },
        {
            "name": "retrain_on_high_drift",
            "priority": 80,
            "description": "High-severity drift requires retraining.",
            "when": {
                "any": [
                    {"field": "max_drift_severity", "op": "eq", "value": "HIGH"},
                    {"field": "recommendation_retrain", "op": "eq", "value": True},
                ]
            },
            "action": "RETRAIN",
        },
        {
            "name": "rotate_keys_on_crypto_degradation",
            "priority": 70,
            "description": "Crypto posture degradation rotates signing keys.",
            "when": {"all": [{"field": "recommendation_rotate_keys", "op": "eq", "value": True}]},
            "action": "ROTATE_KEYS",
        },
        {
            "name": "escalate_on_agent_recommendation",
            "priority": 90,
            "description": "An agent explicitly recommending escalation requires human review rather than silent autonomous acceptance.",
            "when": {"all": [{"field": "recommendation_escalate", "op": "eq", "value": True}]},
            "action": "ESCALATE",
        },
    ],
    "thresholds": {
        "quarantine_risk": 40.0,
        "block_risk": 55.0,
        "escalate_risk": 70.0,
        "max_auto_recoveries": 2,
        "min_security_score": 90.0,
    },
}


def default_policy_engine() -> PolicyEngine:
    return PolicyEngine.from_document(DEFAULT_POLICY_DOCUMENT)

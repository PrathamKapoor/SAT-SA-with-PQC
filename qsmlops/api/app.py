"""Dashboard API backend.

Routes:
    GET  /models, /models/{name}     — registry inventory and per-model detail
    GET  /models/{name}/compare      — artifact/version comparison
    GET  /registry                   — lifecycle state machine overview
    GET  /registry/models            — all versions with persisted trust state
    GET  /registry/versions/{vid}    — version record + latest trust evaluation
    GET  /registry/trust/{vid}       — latest explainable trust report
    POST /registry/trust/{vid}       — request a (re)evaluation of trust
    POST /registry/approve/{vid}     — governed approval via the trust gate
    POST /registry/revoke/{vid}      — revoke a version (audited)
    GET  /verification/{version_id}  — run the five agents on a version
    GET  /agents                     — agent roster + findings from last sweep
    GET  /security                   — keys, suites, crypto posture
    GET  /health                     — platform liveness + ledger integrity
    GET  /incidents                  — quarantines, rollbacks, escalations,
                                        trust evaluations, approval denials
    GET  /dashboard                  — dashboard summary document

Read routes never mutate platform state. The Phase 5 mutation routes
(/registry/trust, /registry/approve, /registry/revoke) delegate entirely to
the governed pipeline/registry code paths — the API never touches registry
state directly, so policy, separation of duties and evidence apply equally.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from qsmlops import __version__ as QSMLOPS_VERSION
from qsmlops.pipeline.selfheal import SelfHealingMLOps
from qsmlops.serving.deployment import DeploymentError
from qsmlops.serving.service import ModelDeploymentService
from qsmlops.registry.registry import (
    ACTIVE_STATES,
    RegistryError,
    STATE_REVOKED,
    STATE_ROLLED_BACK,
)
from qsmlops.scores import compute_scores


class ApproveRequest(BaseModel):
    approver: str


class RevokeRequest(BaseModel):
    reason: str = ""
    actor: str = "api"


class TrustRefreshRequest(BaseModel):
    actor: str = "api"


class DeploymentRequestBody(BaseModel):
    model_name: str | None = None
    version_id: str | None = None
    actor: str = "operator"
    target_environment: str = "production"


class RollbackBody(BaseModel):
    actor: str = "operator"


def register_dashboard_routes(app: FastAPI, pipeline: SelfHealingMLOps) -> None:
    """Attach the dashboard routes to an existing FastAPI application."""
    _last_sweep: dict[str, Any] = {}

    def _require_version(version_id: str) -> dict:
        try:
            return pipeline.registry.get_version(version_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown version {version_id}")

    # ---------------- models ----------------
    @app.get("/models")
    def models() -> dict:
        versions = pipeline.registry.list_versions()
        by_name: dict[str, list] = {}
        for v in versions:
            by_name.setdefault(v["model_name"], []).append(v)
        return {"models": [
            {"name": name, "versions": [
                {"version_id": v["version_id"], "version": v["version"], "state": v["state"],
                 "suite": v["suite_id"], "registered_at": v["registered_at"]}
                for v in rows], "active_deployment": pipeline.registry.active_deployment(name)}
            for name, rows in sorted(by_name.items())
        ]}

    @app.get("/models/{name}")
    def model_detail(name: str) -> dict:
        versions = pipeline.registry.list_versions(name)
        if not versions:
            raise HTTPException(status_code=404, detail=f"unknown model {name}")
        return {"name": name, "versions": versions,
                "active_deployment": pipeline.registry.active_deployment(name)}

    @app.get("/models/{name}/compare")
    def compare(name: str, a: str, b: str) -> dict:
        _require_version(a); _require_version(b)
        return pipeline.registry.compare_versions(a, b)

    # ---------------- registry ----------------
    @app.get("/registry")
    def registry() -> dict:
        versions = pipeline.registry.list_versions()
        states: dict[str, int] = {}
        for v in versions:
            states[v["state"]] = states.get(v["state"], 0) + 1
        return {"state_counts": states, "total_versions": len(versions),
                "active_states": sorted(ACTIVE_STATES),
                "deployments": [d for d in (
                    pipeline.registry.active_deployment(m["model_name"])
                    for m in {v["model_name"]: v for v in versions}.values()) if d]}

    # ---------------- registry (Phase 5) ----------------
    @app.get("/registry/models")
    def registry_models() -> dict:
        versions = pipeline.registry.list_versions()
        return {"models": [
            {
                "version_id": v["version_id"],
                "model_name": v["model_name"],
                "version": v["version"],
                "state": v["state"],
                "suite": v["suite_id"],
                "trust_score": v.get("trust_score"),
                "trust_decision": v.get("trust_decision"),
            }
            for v in versions
        ]}

    @app.get("/registry/versions/{version_id}")
    def registry_version(version_id: str) -> dict:
        _require_version(version_id)
        rec = pipeline.registry.get_version(version_id)
        rec.pop("trust_report", None)
        latest = pipeline.registry.latest_trust(version_id)
        active = pipeline.registry.active_deployment(rec["model_name"])
        return {
            "version": rec,
            "trust": latest,
            "is_active_deployment": bool(active and active["version_id"] == version_id),
        }

    @app.get("/registry/trust/{version_id}")
    def registry_trust(version_id: str) -> dict:
        _require_version(version_id)
        latest = pipeline.registry.latest_trust(version_id)
        if latest is None:
            raise HTTPException(
                status_code=404,
                detail=f"no trust evaluation recorded for {version_id}; POST to re-evaluate",
            )
        return latest

    @app.post("/registry/trust/{version_id}")
    def registry_trust_refresh(version_id: str, body: TrustRefreshRequest | None = None) -> dict:
        _require_version(version_id)
        actor = body.actor if body else "api"
        observations = pipeline.last_observations.get(
            pipeline.registry.get_version(version_id)["model_name"], []
        )
        result = pipeline.registry.trust_evaluation(
            version_id,
            observations=[_rebuild(o) for o in observations] if observations else None,
            actor=actor or "api",
        )
        return result.to_dict()

    @app.post("/registry/approve/{version_id}")
    def registry_approve(version_id: str, body: ApproveRequest) -> dict:
        _require_version(version_id)
        try:
            approval = pipeline.request_approval(version_id, body.approver)
        except (RuntimeError, RegistryError) as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return approval

    @app.post("/registry/revoke/{version_id}")
    def registry_revoke(version_id: str, body: RevokeRequest) -> dict:
        _require_version(version_id)
        # C6: an illegal registry transition (e.g. revoking an already-revoked
        # or rolled-back version) must return a structured 409 conflict, not a
        # 500. The governance reason is preserved in the detail.
        try:
            pipeline.registry.revoke(version_id, body.actor, body.reason)
        except RegistryError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return {
            "version_id": version_id,
            "state": pipeline.registry.get_version(version_id)["state"],
            "revoked_by": body.actor,
            "reason": body.reason,
        }

    # ---------------- monitoring (Phase 7) ----------------
    @app.get("/metrics/{model_name}")
    def metrics_summary(model_name: str) -> dict:
        versions = [v["version_id"] for v in pipeline.registry.list_versions(model_name)]
        if not versions:
            raise HTTPException(status_code=404, detail=f"unknown model {model_name}")
        merged: dict[str, dict] = {}
        # telemetry rows are keyed by model name (stable operator handle);
        # also fold in any per-version rows for completeness
        for key in [model_name, *versions]:
            for name, stats in pipeline.telemetry.summary(key).items():
                cur = merged.setdefault(name, {"count": 0, "last": None,
                                               "min": None, "max": None})
                cur["count"] += stats["count"]
                cur["last"] = stats["last"]
                cur["min"] = stats["min"] if cur["min"] is None else min(cur["min"], stats["min"])
                cur["max"] = stats["max"] if cur["max"] is None else max(cur["max"], stats["max"])
        drift = ([e for e in pipeline.telemetry.drift_history(model_name)]
                 + [e for v in versions for e in pipeline.telemetry.drift_history(v)])[-20:]
        return {"model": model_name, "metrics": merged,
                "drift_history": drift[-20:]}

    @app.get("/drift/{model_name}/attribution")
    def drift_attribution(model_name: str) -> dict:
        """Latest per-feature drift attribution, ranked by severity/score."""
        rows = pipeline.telemetry.latest_feature_attribution(model_name)
        return {"model": model_name,
                "features": [r["detail"] for r in rows], "count": len(rows)}

    @app.get("/performance/{model_name}/rolling")
    def performance_rolling(model_name: str, window: int = 10) -> dict:
        """Rolling performance baselines from recorded telemetry."""
        from qsmlops.config import MONITORING_MIN_HISTORY

        baselines = {
            metric: pipeline.telemetry.rolling_baseline(
                model_name, metric, window=window, min_history=MONITORING_MIN_HISTORY)
            for metric in ("mse", "r2")
        }
        return {"model": model_name, "window": window, "baselines": baselines}

    @app.get("/alerts/{model_name}")
    def alerts_for(model_name: str) -> dict:
        from qsmlops.monitoring.alerts import evaluate as evaluate_alerts
        from qsmlops.config import MONITORING_ROLLING_WINDOW, MONITORING_MIN_HISTORY

        versions = [v["version_id"] for v in pipeline.registry.list_versions(model_name)]
        if not versions:
            raise HTTPException(status_code=404, detail=f"unknown model {model_name}")
        active = pipeline.registry.active_deployment(model_name)
        latest_metrics = pipeline.telemetry.summary(model_name) or (
            pipeline.telemetry.summary(active["version_id"]) if active else {})
        metrics = {k: v["last"] for k, v in latest_metrics.items()}
        drift_summary = pipeline.last_drift_status.get(model_name)
        feature_attributions = pipeline.telemetry.latest_feature_attribution(model_name) or None
        rolling_baselines = [
            pipeline.telemetry.rolling_baseline(
                model_name, metric,
                window=MONITORING_ROLLING_WINDOW,
                min_history=MONITORING_MIN_HISTORY,
            )
            for metric in ("mse", "r2")
        ]
        alerts = evaluate_alerts(
            model_name,
            metrics=metrics or None,
            drift_summary=drift_summary,
            trust_decision=(pipeline.registry.get_version(versions[-1])["state"] == "QUARANTINED"
                            and "QUARANTINED") or None,
            feature_attributions=feature_attributions,
            rolling_baselines=[rb for rb in rolling_baselines if rb.get("sufficient")] or None,
        )
        return {"model": model_name, "alerts": [a.to_dict() for a in alerts],
                "count": len(alerts)}

    # ---------------- deployment (Phase 6) ----------------
    @app.post("/deployment/request")
    def deployment_request(body: DeploymentRequestBody) -> dict:
        """Governed deployment request: every gate runs; refusals return a
        structured 409 with the failed checks. Promotion is performed by the
        registry via pipeline.deployment (never by this handler)."""
        try:
            return pipeline.request_deployment(
                model_name=body.model_name,
                version_id=body.version_id,
                actor=body.actor,
                target_environment=body.target_environment,
            )
        except DeploymentError as exc:
            raise HTTPException(status_code=409, detail=exc.to_dict())

    @app.get("/deployment/status/{model_name}")
    def deployment_status(model_name: str) -> dict:
        active = pipeline.registry.active_deployment(model_name)
        if not active:
            raise HTTPException(status_code=404, detail=f"no active deployment for {model_name}")
        latest_trust = pipeline.registry.latest_trust(active["version_id"])
        serving_ok = True
        detail = ""
        try:
            ModelDeploymentService(pipeline.registry).load(model_name)
        except Exception as exc:  # serving refused the active deployment
            serving_ok = False
            detail = f"{type(exc).__name__}: {exc}"
        return {
            "model": model_name,
            "active_deployment": active,
            "serving_healthy": serving_ok,
            "serving_detail": detail,
            "trust_decision": (latest_trust or {}).get("trust_decision"),
        }

    @app.get("/deployment/validation/{version_id}")
    def deployment_validation(version_id: str, actor: str = "api", target: str = "production") -> dict:
        _require_version(version_id)
        report = pipeline.validate_deployment(version_id, actor=actor, target_environment=target)
        return report

    @app.post("/deployment/rollback/{model_name}")
    def deployment_rollback(model_name: str, body: RollbackBody) -> dict:
        prev = pipeline.registry.rollback(model_name, body.actor)
        if prev is None:
            raise HTTPException(status_code=409, detail=f"no previous version to restore for {model_name}")
        return {"model": model_name, "restored_version_id": prev,
                "state": pipeline.registry.get_version(prev)["state"], "actor": body.actor}

    # ---------------- verification ----------------
    @app.get("/verification/{version_id}")
    def verification(version_id: str) -> dict:
        _require_version(version_id)
        result = pipeline.evaluate_version(version_id)
        _last_sweep["version_id"] = version_id
        _last_sweep["result"] = result
        return result

    # ---------------- agents ----------------
    @app.get("/agents")
    def agents() -> dict:
        roster = [{"name": a.name, "class": type(a).__name__} for a in pipeline.agents]
        findings = []
        if _last_sweep.get("result"):
            for obs in _last_sweep["result"]["observations"]:
                for f in obs["findings"]:
                    findings.append({"agent": obs["agent"], **f})
        elif pipeline.registry.list_versions():
            latest = pipeline.registry.list_versions()[-1]
            result = pipeline.evaluate_version(latest["version_id"])
            _last_sweep.update({"version_id": latest["version_id"], "result": result})
            for obs in result["observations"]:
                for f in obs["findings"]:
                    findings.append({"agent": obs["agent"], **f})
        return {"agents": roster, "findings": findings,
                "last_sweep_version": _last_sweep.get("version_id")}

    # ---------------- security ----------------
    @app.get("/security")
    def security() -> dict:
        keys = pipeline.keystore.list_records(include_inactive=True)
        suites = pipeline.agility.audit_inventory({
            v["suite_id"]: 1 for v in pipeline.registry.list_versions()
        }) if pipeline.registry.list_versions() else {}
        return {
            "keys": [
                {"key_id": r.key_id, "role": r.role, "algorithm": r.algorithm_id,
                 "version": r.version, "status": r.status, "owner": r.owner,
                 "age_days": round(r.age_days, 1),
                 "expires_at": r.expires_at,
                 "expired": r.is_expired()}
                for r in keys
            ],
            "suite_inventory": suites,
            "default_suite": pipeline.agility.default_suite,
            # Phase 2: explicit runtime introspection of the active crypto
            # policy (algorithm family/identifier/security level/configured
            # vs. auto-selected) with no secrets — see AgilityEngine.effective_policy.
            "crypto_policy": pipeline.agility.effective_policy(),
        }

    # ---------------- health ----------------
    @app.get("/health")
    def health() -> dict:
        ok, msg = pipeline.ledger.verify_chain()
        versions = pipeline.registry.list_versions()
        return {"status": "ok" if ok else "ledger_broken",
                "ledger": {"chain_ok": ok, "message": msg, "head": pipeline.ledger.head()},
                "versions": len(versions),
                "learner": pipeline.learner.summary()}

    # ---------------- evidence packet retrieval (F1) ----------------
    @app.get("/evidence/packet/{packet_id}")
    def get_evidence_packet(packet_id: str) -> dict:
        """Retrieve a persisted VerificationPacket by packet_id (content-addressed, digest-verified)."""
        from fastapi import HTTPException

        pkt = pipeline.ledger.get_packet(packet_id)
        if pkt is not None:
            return pkt.to_dict()
        # Distinguish not-found vs integrity failure
        entry = pipeline.ledger.find_by_packet(packet_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="packet_id not found")
        ok, msg = pipeline.ledger.verify_packet(packet_id)
        # Missing or tampered → 404 with integrity detail (never 500)
        raise HTTPException(status_code=404, detail=msg)

    @app.get("/evidence/packets")
    def list_evidence_packets() -> dict:
        ids = pipeline.ledger.list_packet_ids()
        return {"packet_ids": ids, "count": len(ids)}

    @app.get("/evidence/packet/by-digest/{digest}")
    def get_evidence_packet_by_digest(digest: str) -> dict:
        from fastapi import HTTPException

        pkt = pipeline.ledger.get_packet_by_digest(digest)
        if pkt is None:
            raise HTTPException(status_code=404, detail="packet digest not found or corrupted")
        return pkt.to_dict()

    # ---------------- incidents ----------------
    @app.get("/incidents")
    def incidents() -> dict:
        interesting = {
            "state_transition",
            "escalation",
            "verification_packet",
            "trust_evaluation",
            "approval_denied",
        }
        events = []
        for entry in pipeline.ledger.iter_entries():
            record = entry.get("record", {})
            rtype = record.get("type", "")
            if rtype not in interesting:
                continue
            decision = record.get("decision", record.get("to", ""))
            if rtype == "state_transition" and record.get("to") in ("REGISTERED", "VERIFIED"):
                continue
            events.append({
                "seq": entry["seq"], "at": entry["timestamp"], "type": rtype,
                "model": record.get("model", ""), "decision": decision,
                "reason": record.get("reason", record.get("objective", "")),
            })
        events.reverse()
        return {"incidents": events, "count": len(events)}

    # ---------------- dashboard summary ----------------
    @app.get("/dashboard")
    def dashboard() -> dict:
        versions = pipeline.registry.list_versions()
        models = sorted({v["model_name"] for v in versions})
        active_deployments = []
        per_model = []
        for name in models:
            active = pipeline.registry.active_deployment(name)
            if active:
                active_deployments.append({
                    "model": name, "version_id": active["version_id"],
                    "version": active["version"], "deployed_at": active["deployed_at"],
                })
            latest = [v for v in versions if v["model_name"] == name][-1]
            obs = pipeline.last_observations.get(name, [])
            scores = {"security_score": None, "trust_score": None}
            drift = pipeline.last_drift_status.get(name, {"status": "NO_DATA", "max_severity": "NONE"})
            if obs:
                computed = compute_scores([_rebuild(o) for o in obs])
                scores = computed
            per_model.append({"model": name, "latest_state": latest["state"],
                              "scores": scores, "drift": drift,
                              "consecutive_failures": pipeline.learner.consecutive_failures(name)})
        agent_findings = [
            {"model": name, "agent": o["agent"], "name": f["name"], "passed": f["passed"],
             "severity": f["severity"], "risk": f.get("risk", ""),
             "recommendation": f.get("recommendation", "")}
            for name in models for o in pipeline.last_observations.get(name, [])
            for f in o["findings"]
        ]
        supervisor_actions = [
            {"model": o.get("model"), "decision": o["decision"], "success": o["success"],
             "detail": o["detail"], "at": o["at"]}
            for o in pipeline.learner._state.get("outcomes", [])[-20:]
        ]
        ok, msg = pipeline.ledger.verify_chain()
        return {
            "models": per_model,
            "active_deployments": active_deployments,
            "drift_status": {"monitored_models": len(models),
                             "per_model": {name: pipeline.last_drift_status.get(
                                 name, {"status": "NO_DATA"}) for name in models}},
            "agent_findings": agent_findings,
            "supervisor_actions": supervisor_actions,
            "ledger_ok": ok,
        }

    def _rebuild(o: dict):
        from qsmlops.agents.base import Finding, Observation

        obs = Observation(agent=o["agent"], subject_id=o.get("subject_id", ""),
                          recommendation=o.get("recommendation", ""))
        obs.findings = [Finding.from_dict(f) for f in o.get("findings", [])]
        return obs


def create_app(pipeline: SelfHealingMLOps) -> FastAPI:
    """Standalone dashboard app (kept for backward compatibility)."""
    app = FastAPI(title="qsmlops dashboard", version=QSMLOPS_VERSION)
    register_dashboard_routes(app, pipeline)
    return app

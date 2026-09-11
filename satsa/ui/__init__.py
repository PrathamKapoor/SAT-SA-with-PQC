"""SAT-SA web UI — FastAPI application exposing the supervisory
analytics surface to an operator (entity risk, findings, peer
benchmarks, review queue, reports, trust verification).

The UI is air-gapped: it renders Jinja2 templates and serves them
along with static assets. No CDN dependencies, no remote fonts, no
JavaScript frameworks — vanilla JS + the platform's own CSS so
the operator can audit exactly what runs in the browser.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from satsa import __version__ as SATSA_VERSION
from satsa import security as satsa_security
from qsmlops.security.permissions.model import ANALYSIS_RUN, DECISION_RECORD


HERE = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(HERE / "templates"))


def _loadjson(value):
    import json
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return {}


TEMPLATES.env.filters["loadjson"] = _loadjson


def create_app(service, *, trust_key_dir: Optional[Path] = None) -> FastAPI:
    """Build the FastAPI app bound to a ``SatsaService``. The
    trust key dir is the same directory passed to
    ``SatsaService.run_analysis`` for PQC signing; the UI uses it
    to verify receipts on demand."""
    svc = service
    db = svc._db  # type: ignore[attr-defined]

    app = FastAPI(title="SAT-SA", version=SATSA_VERSION)
    app.state.service = svc
    app.state.trust_key_dir = Path(trust_key_dir) if trust_key_dir else None

    # Identity/auth: wires the UI to the existing qsmlops identity
    # system (satsa/security.py) instead of trusting a caller-supplied
    # header for the review audit trail. The identity ledger lives
    # alongside the trust keys (or a local default if no key dir was
    # given, e.g. an in-memory-DB smoke test).
    identity_ledger_dir = (
        Path(trust_key_dir) if trust_key_dir else Path(".satsa_identity")
    )
    identity_service = satsa_security.build_identity_service(
        db, ledger_dir=identity_ledger_dir)
    app.state.identity_service = identity_service

    app.mount("/static", StaticFiles(directory=str(HERE / "static")),
              name="static")

    # ---- helpers --------------------------------------------------

    def _row(sql, params=()):
        if hasattr(db, "connect"):
            db.connect()
        return db.query_one(sql, params)

    def _all(sql, params=()):
        if hasattr(db, "connect"):
            db.connect()
        return [dict(r) for r in db.query_all(sql, params)]

    def _finding_row(finding_id: str):
        r = _row("SELECT * FROM satsa_findings WHERE id=?", (finding_id,))
        if not r:
            raise HTTPException(404, "finding not found")
        return r

    # ---- HTML pages ----------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    def overview(request: Request):
        entities = _all(
            "SELECT id, display_name, sector, environment_class"
            " FROM satsa_entities ORDER BY display_name")
        # latest risk per entity
        entity_risks: dict = {}
        for e in entities:
            prof = svc.compute_risk(e["id"])
            if prof.run_id is None:
                continue
            entity_risks[e["id"]] = prof
        ranked = sorted(
            entity_risks.values(),
            key=lambda p: p.total_score, reverse=True)
        totals = {
            "entities": len(entities),
            "assessments": _row("SELECT COUNT(*) AS c FROM satsa_assessments")["c"],
            "submissions": _row("SELECT COUNT(*) AS c FROM satsa_submissions")["c"],
            "runs": _row("SELECT COUNT(*) AS c FROM satsa_runs")["c"],
            "findings": _row("SELECT COUNT(*) AS c FROM satsa_findings")["c"],
            "signals": _row("SELECT COUNT(*) AS c FROM satsa_findings"
                             " WHERE state='signal'")["c"],
        }
        # Trust check: latest run is verified if receipts exist
        trust_ok = bool(_row(
            "SELECT COUNT(*) AS c FROM satsa_trust_receipts"
            " WHERE subject_type='run'"))
        return TEMPLATES.TemplateResponse(request, "overview.html", {
            "sat_version": SATSA_VERSION, "totals": totals,
            "ranked": ranked, "entities": entities,
            "trust_ok": trust_ok,
        })

    @app.get("/entities", response_class=HTMLResponse)
    def entities_page(request: Request):
        entities = _all(
            "SELECT id, display_name, sector, environment_class"
            " FROM satsa_entities ORDER BY display_name")
        rows = []
        for e in entities:
            prof = svc.compute_risk(e["id"])
            rows.append({
                "entity": e,
                "risk": prof,
            })
        return TEMPLATES.TemplateResponse(request, "entities.html", {
            "sat_version": SATSA_VERSION, "rows": rows,
        })

    @app.get("/entities/{entity_id}", response_class=HTMLResponse)
    def entity_detail(entity_id: str, request: Request):
        e = _row("SELECT * FROM satsa_entities WHERE id=?", (entity_id,))
        if not e:
            raise HTTPException(404, "entity not found")
        assessments = _all(
            "SELECT * FROM satsa_assessments WHERE entity_id=?"
            " ORDER BY period_start DESC", (entity_id,))
        prof = svc.compute_risk(entity_id)
        # latest run findings
        run_id = prof.run_id
        findings = []
        if run_id:
            findings = _all(
                "SELECT f.*, o.worker_name FROM satsa_findings f"
                " JOIN satsa_observations o ON o.id=f.observation_id"
                " WHERE o.run_id=? ORDER BY f.created_at", (run_id,))
        return TEMPLATES.TemplateResponse(request, "entity_detail.html", {
            "sat_version": SATSA_VERSION, "entity": e, "assessments": assessments,
            "risk": prof, "findings": findings,
        })

    @app.get("/findings", response_class=HTMLResponse)
    def findings_page(request: Request, state: str = "signal",
                       rule: str = ""):
        # latest-run findings for the run selected in the session
        # (we just pick the most recent completed run for the demo)
        run_row = _row(
            "SELECT * FROM satsa_runs WHERE status IN ('completed','partial')"
            " ORDER BY created_at DESC LIMIT 1")
        findings = []
        if run_row:
            findings = _all(
                "SELECT f.*, o.worker_name, o.entity_id, o.assessment_id,"
                " e.display_name FROM satsa_findings f"
                " JOIN satsa_observations o ON o.id=f.observation_id"
                " JOIN satsa_entities e ON e.id=o.entity_id"
                " WHERE o.run_id=? AND f.state=?"
                " ORDER BY f.created_at", (run_row["id"], state))
        if rule:
            findings = [f for f in findings if rule in f.get("rule_or_category", "")]
        rules = sorted({f.get("rule_or_category", "") for f in findings})
        return TEMPLATES.TemplateResponse(request, "findings.html", {
            "sat_version": SATSA_VERSION, "findings": findings,
            "state": state, "rule": rule, "rules": rules,
        })

    @app.get("/findings/{finding_id}", response_class=HTMLResponse)
    def finding_detail(finding_id: str, request: Request):
        f = _finding_row(finding_id)
        obs = _row("SELECT * FROM satsa_observations WHERE id=?",
                   (f["observation_id"],))
        evidence_refs = json.loads(f.get("evidence_refs_json") or "[]")
        evidence = []
        for ref in evidence_refs:
            sr = _row("SELECT * FROM satsa_source_records WHERE id=?",
                      (ref,))
            if sr:
                evidence.append(dict(sr))
        confidence = json.loads(f.get("confidence_json") or "{}")
        reviews = svc.review_history(finding_id)
        from satsa.analysis.recommend import recommend
        rec = recommend(f)
        return TEMPLATES.TemplateResponse(request, "finding_detail.html", {
            "sat_version": SATSA_VERSION, "finding": f, "observation": obs,
            "evidence": evidence, "confidence": confidence,
            "reviews": reviews, "recommendation": rec,
        })

    @app.post("/findings/{finding_id}/review")
    async def post_review(finding_id: str, request: Request):
        # Authenticated + authorized principal only — the audit trail
        # binds a review decision to a real, verified Identity record
        # (qsmlops.security.identity), never to caller-supplied text.
        # 401 if unauthenticated, 403 if authenticated but lacking
        # decision.record (e.g. a satsa_viewer or satsa_auditor
        # credential). This is enforced server-side and applies
        # identically to a raw HTTP client bypassing the UI form.
        principal = satsa_security.require(
            identity_service, request, DECISION_RECORD)
        form = await request.form()
        action = form.get("action", "").strip()
        reason = form.get("reason", "").strip()
        if action not in ("confirm", "dismiss", "escalate",
                          "annotate", "request_review"):
            raise HTTPException(400, "invalid action")
        # capture the live digest
        from satsa.analysis.run import RunService
        f = _finding_row(finding_id)
        live_digest = RunService._live_digest_for_finding(f)
        prev_id = None
        history = svc.review_history(finding_id)
        if history:
            prev_id = history[-1].id
        entry = svc.record_review(
            finding_id=finding_id,
            principal_identity_id=principal.identity_id,
            action=action, reason=reason,
            finding_content_digest=live_digest,
            previous_revision_id=prev_id,
        )
        # redirect back to the finding page
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"/findings/{finding_id}",
                                status_code=303)

    # ---- authentication ---------------------------------------------

    @app.get("/login", response_class=HTMLResponse)
    def login_page(request: Request, error: str = ""):
        return TEMPLATES.TemplateResponse(request, "login.html", {
            "sat_version": SATSA_VERSION, "error": error,
        })

    @app.post("/login")
    async def login_submit(request: Request):
        from fastapi.responses import RedirectResponse
        form = await request.form()
        token = (form.get("credential") or "").strip()
        try:
            principal = identity_service.authenticate(token)
        except Exception:
            return RedirectResponse(
                url="/login?error=invalid+credential", status_code=303)
        resp = RedirectResponse(url="/", status_code=303)
        # HttpOnly: not readable by page JS, mitigating token theft via
        # XSS. Not marked Secure since this is an air-gapped deployment
        # typically served over plain HTTP on localhost/LAN, not TLS.
        resp.set_cookie(
            satsa_security.COOKIE_NAME, token,
            httponly=True, samesite="lax", path="/")
        return resp

    @app.post("/logout")
    def logout():
        from fastapi.responses import RedirectResponse
        resp = RedirectResponse(url="/login", status_code=303)
        resp.delete_cookie(satsa_security.COOKIE_NAME, path="/")
        return resp

    @app.get("/benchmarks", response_class=HTMLResponse)
    def benchmarks_page(request: Request):
        # show all peer_benchmark findings
        rows = _all(
            "SELECT f.*, o.worker_name, e.display_name"
            " FROM satsa_findings f"
            " JOIN satsa_observations o ON o.id=f.observation_id"
            " JOIN satsa_entities e ON e.id=o.entity_id"
            " WHERE f.rule_or_category LIKE 'peer_benchmark.%'"
            " ORDER BY e.display_name, f.created_at")
        return TEMPLATES.TemplateResponse(request, "benchmarks.html", {
            "sat_version": SATSA_VERSION, "rows": rows,
        })

    @app.get("/queue", response_class=HTMLResponse)
    def review_queue(request: Request):
        # entity + finding priority
        entity_pri = svc.prioritize_entities()
        # build a flat list of all findings of the latest run of
        # each entity, with their finding priority
        all_findings = []
        for ep in entity_pri:
            e_row = _row("SELECT * FROM satsa_entities WHERE id=?",
                         (ep.entity_id,))
            if not e_row:
                continue
            latest = _row(
                "SELECT * FROM satsa_runs WHERE entity_id=?"
                " ORDER BY created_at DESC LIMIT 1", (ep.entity_id,))
            if not latest:
                continue
            for f in svc.prioritize_findings(latest["id"]):
                all_findings.append({
                    "entity": e_row, "priority": ep,
                    "finding": f,
                })
        all_findings.sort(
            key=lambda r: r["finding"].priority_score, reverse=True)
        return TEMPLATES.TemplateResponse(request, "queue.html", {
            "sat_version": SATSA_VERSION, "rows": all_findings,
        })

    @app.get("/evidence", response_class=HTMLResponse)
    def evidence_page(request: Request):
        rows = _all(
            "SELECT * FROM satsa_source_records"
            " ORDER BY submission_id, locator LIMIT 200")
        return TEMPLATES.TemplateResponse(request, "evidence.html", {
            "sat_version": SATSA_VERSION, "rows": rows,
        })

    @app.get("/system", response_class=HTMLResponse)
    def system_page(request: Request):
        # latest run for the trust verification preview
        latest = _row(
            "SELECT * FROM satsa_runs ORDER BY created_at DESC LIMIT 1")
        trust_report = None
        if latest and app.state.trust_key_dir is not None:
            try:
                trust_report = svc.verify_run(latest["id"],
                                              app.state.trust_key_dir)
            except Exception as exc:
                trust_report = {"error": str(exc)}
        counts = {
            "runs": _row("SELECT COUNT(*) AS c FROM satsa_runs")["c"],
            "observations": _row(
                "SELECT COUNT(*) AS c FROM satsa_observations")["c"],
            "findings": _row(
                "SELECT COUNT(*) AS c FROM satsa_findings")["c"],
            "jobs": _row("SELECT COUNT(*) AS c FROM satsa_jobs")["c"],
            "receipts": _row(
                "SELECT COUNT(*) AS c FROM satsa_trust_receipts")["c"],
            "reviews": _row(
                "SELECT COUNT(*) AS c FROM satsa_review_decisions")["c"],
        }
        return TEMPLATES.TemplateResponse(request, "system.html", {
            "sat_version": SATSA_VERSION, "latest": latest,
            "trust_report": trust_report, "counts": counts,
        })

    @app.get("/architecture", response_class=HTMLResponse)
    def architecture_page(request: Request):
        """The target architecture visualization — Security Data +
        ML/Analytics → Supervisory Agents → Detect / Correlate /
        Assess → Risk Finding → Recommendation → Human Supervisor
        → Action / Decision → TRUST-SAT."""
        from satsa.supervisor import list_agents, RETAINED_MLOPS_AGENTS, SATSA_AGENTS
        return TEMPLATES.TemplateResponse(request, "architecture.html", {
            "sat_version": SATSA_VERSION,
            "mlops_agents": RETAINED_MLOPS_AGENTS,
            "satsa_agents": SATSA_AGENTS,
        })

    @app.get("/agents", response_class=HTMLResponse)
    def agents_page(request: Request):
        """The 26-agent explorer — every retained MLOps agent and
        every SAT-SA supervisory agent, with its inputs, outputs,
        evidence types, and current status."""
        from satsa.supervisor import list_agents
        return TEMPLATES.TemplateResponse(request, "agents.html", {
            "sat_version": SATSA_VERSION,
            "agents": list_agents(),
            "total": len(list_agents()),
        })

    @app.get("/trust", response_class=HTMLResponse)
    def trust_page(request: Request):
        """TRUST-SAT — the integrity foundation. Cryptographic
        posture, latest verification report, evidence chain."""
        latest = _row(
            "SELECT * FROM satsa_runs ORDER BY created_at DESC LIMIT 1")
        trust_report = None
        if latest and app.state.trust_key_dir is not None:
            try:
                trust_report = svc.verify_run(latest["id"],
                                              app.state.trust_key_dir)
            except Exception as exc:
                trust_report = {"error": str(exc)}
        receipt_count = _row(
            "SELECT COUNT(*) AS c FROM satsa_trust_receipts")["c"]
        return TEMPLATES.TemplateResponse(request, "trust.html", {
            "sat_version": SATSA_VERSION,
            "latest": latest,
            "trust_report": trust_report,
            "receipt_count": receipt_count,
            "trust_key_dir": str(app.state.trust_key_dir) if app.state.trust_key_dir else None,
        })

    @app.get("/decisions", response_class=HTMLResponse)
    def decisions_page(request: Request):
        """Human-decision view — the supervisory workflow and its
        audit trail."""
        # Note: scoped_subjects_json stores a JSON array of subject
        # ids, so we LEFT JOIN by extracting it as text. SQLite does
        # not have a JSON-array join operator; we leave entity
        # display_name as a separate query.
        reviews = _all(
            "SELECT r.*, f.rule_or_category FROM"
            " satsa_review_decisions r"
            " LEFT JOIN satsa_findings f ON f.id = r.finding_id"
            " ORDER BY r.occurred_at DESC LIMIT 100")
        review_count = _row(
            "SELECT COUNT(*) AS c FROM satsa_review_decisions")["c"]
        return TEMPLATES.TemplateResponse(request, "decisions.html", {
            "sat_version": SATSA_VERSION,
            "reviews": reviews,
            "review_count": review_count,
        })

    @app.get("/security-data", response_class=HTMLResponse)
    def security_data_page(request: Request):
        """Security-data view — submissions, files, evidence categories,
        completeness."""
        submissions = _all(
            "SELECT s.*, e.display_name FROM satsa_submissions s"
            " JOIN satsa_entities e ON e.id = s.entity_id"
            " ORDER BY s.created_at DESC LIMIT 50")
        counts = {
            "submissions": _row(
                "SELECT COUNT(*) AS c FROM satsa_submissions")["c"],
            "alerts": _row("SELECT COUNT(*) AS c FROM satsa_alerts")["c"],
            "cases": _row("SELECT COUNT(*) AS c FROM satsa_cases")["c"],
            "investigation_steps": _row(
                "SELECT COUNT(*) AS c FROM satsa_investigation_steps")["c"],
            "escalations": _row(
                "SELECT COUNT(*) AS c FROM satsa_escalations")["c"],
            "dispositions": _row(
                "SELECT COUNT(*) AS c FROM satsa_dispositions")["c"],
            "assets": _row("SELECT COUNT(*) AS c FROM satsa_assets")["c"],
        }
        return TEMPLATES.TemplateResponse(request, "security_data.html", {
            "sat_version": SATSA_VERSION,
            "submissions": submissions,
            "counts": counts,
        })

    @app.get("/pipeline", response_class=HTMLResponse)
    def pipeline_page(request: Request):
        """Analytics pipeline view — Detect → Correlate → Assess →
        Reason drill-down, with the actual worker names mapped to
        each stage."""
        from satsa.supervisor import SATSA_AGENTS
        stage_agents = {
            "Detect": [a for a in SATSA_AGENTS
                       if a.agent_id in {
                           "satsa.execution_gap",
                           "satsa.negative_space",
                           "satsa.anomaly",
                           "satsa.peer_benchmark",
                           "satsa.coverage_gap",
                       }],
            "Correlate": [a for a in SATSA_AGENTS
                          if a.agent_id in {
                              "satsa.cross_entity_insights",
                              "satsa.case_similarity",
                              "satsa.drift",
                              "satsa.evidence_completeness",
                          }],
            "Assess": [a for a in SATSA_AGENTS
                        if a.agent_id in {
                            "satsa.fusion",
                            "satsa.prioritization",
                            "satsa.recommendation",
                        }],
            "Reason & Trust": [a for a in SATSA_AGENTS
                               if a.agent_id in {
                                   "satsa.review_workflow",
                                   "satsa.trust_provenance",
                                   "satsa.validation",
                               }],
        }
        return TEMPLATES.TemplateResponse(request, "pipeline.html", {
            "sat_version": SATSA_VERSION,
            "stage_agents": stage_agents,
        })

    @app.get("/reports/{entity_id}", response_class=HTMLResponse)
    def report(entity_id: str, request: Request):
        from satsa.analysis.report import render_report
        e = _row("SELECT * FROM satsa_entities WHERE id=?", (entity_id,))
        if not e:
            raise HTTPException(404, "entity not found")
        prof = svc.compute_risk(entity_id)
        if prof.run_id is None:
            return HTMLResponse(
                "<html><body><h1>No run</h1>"
                f"<p>{e['display_name']} has no analysis run yet.</p>"
                "<p><a href='/'>back</a></p></body></html>")
        findings = _all(
            "SELECT f.*, o.worker_name FROM satsa_findings f"
            " JOIN satsa_observations o ON o.id=f.observation_id"
            " WHERE o.run_id=? ORDER BY f.created_at", (prof.run_id,))
        assessments = _all(
            "SELECT * FROM satsa_assessments WHERE entity_id=?"
            " ORDER BY period_start DESC", (entity_id,))
        html = render_report(
            entity=e, assessments=assessments, risk=prof, findings=findings,
            generated_at=__import__("time").time())
        return HTMLResponse(html)

    # ---- ingest (browser upload) -----------------------------------
    # Same SatsaService.submit()/run_analysis() call path as `sat-sa
    # ingest`/`sat-sa analyze` — this route contains no ingestion or
    # analysis logic of its own, only form handling.

    UPLOAD_CATEGORIES = (
        "alerts", "cases", "investigation_steps", "escalations",
        "dispositions", "assets")

    @app.get("/ingest", response_class=HTMLResponse)
    def ingest_form(request: Request, error: str = ""):
        principal = satsa_security.resolve_principal(request, identity_service)
        can_ingest = principal is not None and principal.has_permission(ANALYSIS_RUN)
        return TEMPLATES.TemplateResponse(request, "ingest.html", {
            "sat_version": SATSA_VERSION, "error": error,
            "can_ingest": can_ingest,
        })

    @app.post("/ingest")
    async def ingest_submit(request: Request):
        from urllib.parse import quote
        from fastapi.responses import RedirectResponse

        # Authenticated + authorized (ANALYSIS_RUN) only — ingesting
        # real evidence and triggering analysis is a state-changing
        # action, gated the same way record_review is (satsa/security.py).
        satsa_security.require(identity_service, request, ANALYSIS_RUN)

        form = await request.form()
        entity_name = str(form.get("entity_name") or "").strip()
        sector = str(form.get("sector") or "").strip()
        environment = str(form.get("environment") or "").strip()
        source_system = str(form.get("source_system") or "").strip() or "ui-upload"

        from satsa.ingest.normalize import parse_timestamp, TimestampError
        try:
            period_start = parse_timestamp(form.get("period_start"))
            period_end = parse_timestamp(form.get("period_end"))
        except TimestampError as exc:
            return RedirectResponse(
                url=f"/ingest?error={quote(str(exc))}", status_code=303)
        if not entity_name or period_start is None or period_end is None:
            return RedirectResponse(
                url="/ingest?error=" + quote(
                    "entity name and both period bounds are required"),
                status_code=303)

        import shutil
        import tempfile
        tmpdir = Path(tempfile.mkdtemp(prefix="satsa-ui-ingest-"))
        try:
            files: dict = {}
            for category in UPLOAD_CATEGORIES:
                upload = form.get(category)
                filename = getattr(upload, "filename", "") if upload else ""
                if not filename:
                    continue
                suffix = Path(filename).suffix or ".csv"
                dest = tmpdir / f"{category}{suffix}"
                dest.write_bytes(await upload.read())
                files[category] = dest

            if "alerts" not in files:
                return RedirectResponse(
                    url="/ingest?error=" + quote("an alerts file is required"),
                    status_code=303)

            try:
                entity = svc.register_entity(
                    entity_name, sector=sector, environment_class=environment)
                assessment = svc.open_assessment(
                    entity.id, period_start, period_end)
                svc.submit(assessment.id, files, source_system=source_system)
                svc.run_analysis(
                    entity.id, assessment.id,
                    trust_key_dir=app.state.trust_key_dir)
            except Exception as exc:  # noqa: BLE001 — surface any real
                # ingestion/domain-validation error to the operator
                # rather than a raw 500.
                return RedirectResponse(
                    url=f"/ingest?error={quote(str(exc))}", status_code=303)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        return RedirectResponse(url=f"/entities/{entity.id}", status_code=303)

    # ---- demo loader ----------------------------------------------

    @app.post("/demo/load", response_class=HTMLResponse)
    async def load_demo(request: Request):
        """Load the committed demo dataset (5 CSEs), ingest + run
        analytics on each, and return a summary page. This is the
        'Load Demonstration Assessment' button the spec calls for."""
        from satsa.ui.demo import load_demo_assessment
        result = load_demo_assessment(svc, app.state.trust_key_dir)
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"/demo/result?run_id={result['run_id']}",
                                status_code=303)

    @app.get("/demo/result", response_class=HTMLResponse)
    def demo_result(run_id: str, request: Request):
        run = _row("SELECT * FROM satsa_runs WHERE id=?", (run_id,))
        if not run:
            raise HTTPException(404, "run not found")
        e = _row("SELECT * FROM satsa_entities WHERE id=?",
                 (run["entity_id"],))
        prof = svc.compute_risk(run["entity_id"])
        findings = _all(
            "SELECT f.*, o.worker_name FROM satsa_findings f"
            " JOIN satsa_observations o ON o.id=f.observation_id"
            " WHERE o.run_id=? ORDER BY f.created_at", (run_id,))
        return TEMPLATES.TemplateResponse(request, "demo_result.html", {
            "sat_version": SATSA_VERSION, "run": run, "entity": e,
            "risk": prof, "findings": findings,
        })

    # ---- JSON helpers (small, for the UI's progressive enhancement)

    @app.get("/api/entities")
    def api_entities():
        return JSONResponse(_all(
            "SELECT id, display_name, sector, environment_class"
            " FROM satsa_entities ORDER BY display_name"))

    @app.get("/api/entities/{entity_id}/risk")
    def api_entity_risk(entity_id: str):
        prof = svc.compute_risk(entity_id)
        return JSONResponse(prof.to_dict() if prof else {})

    return app

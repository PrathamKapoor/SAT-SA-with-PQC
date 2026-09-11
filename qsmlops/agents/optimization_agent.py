"""Optimization Agent (Phase 9, pipeline-efficiency scope).

Per the roadmap the archetype covers *pipeline* efficiency. The only
optimization evidence this repository genuinely produces today is registry
housekeeping: duplicate artifact reuse across versions and stale
never-promoted versions. Findings are informational housekeeping signals —
never lifecycle mutations.
"""
from __future__ import annotations

import time

from qsmlops.agents.base import BaseAgent, Evidence, Observation, make_finding


class OptimizationAgent(BaseAgent):
    name = "optimization-agent"

    def __init__(self, registry, stale_days: float = 7.0) -> None:
        self.registry = registry
        self.stale_days = stale_days

    def observe(self, context: dict) -> Observation:
        findings = []
        subject = context.get("subject_id", "")
        versions = self.registry.list_versions()

        # 1. duplicate artifact reuse across versions ----------------------
        by_digest: dict[str, list[str]] = {}
        for v in versions:
            by_digest.setdefault(v["artifact_digest"], []).append(
                f"{v['model_name']}@v{v['version']}")
        duplicates = {d: refs for d, refs in by_digest.items() if len(refs) > 1}
        findings.append(make_finding(
            "no_duplicate_artifacts", not duplicates,
            "LOW",
            f"{len(duplicates)} artifact digest(s) reused across versions"
            if duplicates else "every version trains its own artifact",
            observation=(f"duplicate artifacts detected: "
                         f"{'; '.join(f'{d[:12]}… -> {refs}' for d, refs in list(duplicates.items())[:3])}"
                         if duplicates else "no duplicate training artifacts"),
            evidence=[Evidence("model_registry", "log",
                               {"duplicate_digests": len(duplicates)})],
            confidence=1.0,
        ))

        # 2. stale never-approved versions (pipeline housekeeping) ---------
        now = time.time()
        stale = [
            f"{v['model_name']}@v{v['version']}"
            for v in versions
            if v["state"] == "REGISTERED"
            and (now - v.get("registered_at", now)) / 86400 >= self.stale_days
        ]
        findings.append(make_finding(
            "no_stale_registered_versions", not stale,
            "LOW",
            f"{len(stale)} REGISTERED version(s) older than {self.stale_days:.0f}d"
            if stale else "no stale un-promoted versions",
            observation=(f"stale REGISTERED versions lingering: "
                         f"{', '.join(stale[:4])}" if stale else
                         "registry housekeeping clean"),
            evidence=[Evidence("model_registry", "log", {"stale": stale})],
            confidence=0.95,
            recommendation="REVIEW_PIPELINE" if stale else "",
        ))

        # 3. subject-version storage dedup hint ----------------------------
        rec = context.get("version_record") or {}
        dup_self = len(by_digest.get(rec.get("artifact_digest", ""), [])) > 1 \
            if rec else False
        findings.append(make_finding(
            "subject_artifact_unique", not dup_self,
            "INFO" if False else "LOW",
            "" if not dup_self else
            "this version reuses an existing artifact digest",
            observation=("subject artifact unique in registry"
                         if not dup_self else
                         "subject reuses an artifact already trained elsewhere"),
            evidence=[Evidence("model_registry", "log",
                               {"artifact_digest": rec.get("artifact_digest", "")})],
            confidence=1.0,
        ))

        failed = [f for f in findings if not f.passed]
        rec = "OPTIMIZE" if failed else "ACCEPT"
        return Observation(agent=self.name, subject_id=subject,
                           recommendation=rec, findings=findings,
                           notes="registry housekeeping sweep")

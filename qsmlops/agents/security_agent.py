"""Security Agent: dependency vulnerabilities and artifact integrity."""
from __future__ import annotations

import re

from qsmlops.agents.base import BaseAgent, Evidence, Finding, Observation, make_finding
from qsmlops.artifacts.store import ArtifactStore
from qsmlops.supplychain.bom import QMLBOM

ADVISORY_DB: list[dict] = [
    {
        "package": "torch",
        "vulnerable": "<2.4.0",
        "cve": "CVE-2025-31234",
        "severity": "HIGH",
        "summary": "arbitrary code execution via crafted pickle payload",
    },
    {
        "package": "tensorflow",
        "vulnerable": "<2.16.1",
        "cve": "CVE-2024-36500",
        "severity": "CRITICAL",
        "summary": "heap overflow in tensor parsing",
    },
    {
        "package": "transformers",
        "vulnerable": "<4.42.0",
        "cve": "CVE-2024-00099",
        "severity": "HIGH",
        "summary": "unsafe deserialization of checkpoint files",
    },
    {
        "package": "openssl",
        "vulnerable": "<3.0.14",
        "cve": "CVE-2024-55551",
        "severity": "MEDIUM",
        "summary": "timing side channel in session handling",
    },
]


def _version_tuple(v: str) -> tuple:
    parts = re.findall(r"\d+", v)
    return tuple(int(p) for p in parts) if parts else (0,)


def _satisfies_vulnerable(version: str, constraint: str) -> bool:
    m = re.fullmatch(r"(<=|<|>=|>|==)\s*(.+)", constraint.strip())
    if not m:
        return False
    op, target = m.group(1), _version_tuple(m.group(2))
    cur = _version_tuple(version)
    return {
        "<": cur < target,
        "<=": cur <= target,
        ">": cur > target,
        ">=": cur >= target,
        "==": cur == target,
    }[op]


class SecurityAgent(BaseAgent):
    name = "security-agent"

    def __init__(self, artifacts: ArtifactStore, advisory_db: list[dict] | None = None) -> None:
        self.artifacts = artifacts
        self.advisory_db = advisory_db or ADVISORY_DB

    def observe(self, context: dict) -> Observation:
        bom = context["bom"]
        if isinstance(bom, dict):
            bom = QMLBOM.from_dict(bom)
        findings: list[Finding] = []
        for dep in bom.by_kind("dependency"):
            for adv in self.advisory_db:
                if adv["package"] != dep.name or not dep.version:
                    continue
                if _satisfies_vulnerable(dep.version, adv["vulnerable"]):
                    findings.append(
                        make_finding(
                            f"dependency_vulnerability:{dep.name}",
                            False,
                            adv["severity"],
                            f"{adv['cve']}: {adv['summary']} "
                            f"(installed {dep.version}, vulnerable {adv['vulnerable']})",
                            observation=(
                                f"dependency {dep.name}=={dep.version} is affected by "
                                f"{adv['cve']} ({adv['severity']}): {adv['summary']}"
                            ),
                            evidence=[Evidence(
                                "advisory_db", "external",
                                {
                                    "package": dep.name,
                                    "installed_version": dep.version,
                                    "vulnerable_constraint": adv["vulnerable"],
                                    "cve": adv["cve"],
                                    "severity": adv["severity"],
                                    "summary": adv["summary"],
                                },
                                description="matched against platform advisory database",
                            )],
                            confidence=0.9,
                            recommendation="BLOCK_DEPLOYMENT" if adv["severity"] == "CRITICAL" else "ESCALATE",
                        )
                    )
        for entry in bom.entries:
            ok = self.artifacts.verify(entry.digest)
            if not ok:
                try:
                    stored = self.artifacts.get_if_exists(entry.digest)
                except Exception:
                    stored = None
                actual = self.artifacts.digest(stored) if stored is not None else ""
                findings.append(
                    make_finding(
                        f"supplychain_integrity:{entry.name}",
                        False,
                        "CRITICAL",
                        f"{entry.kind} {entry.name!r} missing/corrupted in artifact store",
                        observation=(
                            f"{entry.kind} {entry.name!r} failed integrity check: "
                            f"declared {entry.digest[:16]}… recomputed {actual[:16] or 'MISSING'}…"
                        ),
                        evidence=[Evidence(
                            "artifact_store", "crypto",
                            {
                                "kind": entry.kind,
                                "name": entry.name,
                                "declared_digest": entry.digest,
                                "recomputed_digest": actual,
                            },
                            description="SHA3-256 recomputation against content-addressed store",
                        )],
                        confidence=1.0,
                        recommendation="BLOCK_DEPLOYMENT",
                    )
                )
        vulns_critical = [f for f in findings if not f.passed and f.severity == "CRITICAL"]
        if vulns_critical:
            rec = "BLOCK_DEPLOYMENT"
        elif any(not f.passed for f in findings):
            rec = "ESCALATE"
        else:
            rec = "ACCEPT"
        return Observation(
            agent=self.name,
            subject_id=context.get("subject_id", ""),
            recommendation=rec,
            findings=findings,
        )

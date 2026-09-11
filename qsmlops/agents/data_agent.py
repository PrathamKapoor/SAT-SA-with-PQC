"""Data Agent: verifies dataset integrity against the QML-BOM."""
from __future__ import annotations

from qsmlops.agents.base import BaseAgent, Evidence, Finding, Observation, make_finding
from qsmlops.artifacts.store import ArtifactStore
from qsmlops.supplychain.bom import QMLBOM


class DataAgent(BaseAgent):
    name = "data-agent"

    def __init__(self, artifacts: ArtifactStore) -> None:
        self.artifacts = artifacts

    def observe(self, context: dict) -> Observation:
        bom = context["bom"]
        if isinstance(bom, dict):
            bom = QMLBOM.from_dict(bom)
        datasets = bom.by_kind("dataset")
        findings: list[Finding] = []
        if not datasets:
            findings.append(
                make_finding(
                    "datasets_present", False, "HIGH", "BOM declares no datasets",
                    observation="QML-BOM contains no dataset entries; training provenance unverifiable",
                    evidence=[Evidence("qml_bom", "log", {"entry_count": len(bom.entries)})],
                    confidence=0.99,
                    recommendation="ESCALATE",
                )
            )
        for ds in datasets:
            ok = self.artifacts.verify(ds.digest)
            stored = self.artifacts.get_if_exists(ds.digest)
            actual_digest = self.artifacts.digest(stored) if stored is not None else ""
            findings.append(
                make_finding(
                    f"dataset_integrity:{ds.name}",
                    ok,
                    "CRITICAL" if not ok else "LOW",
                    "digest matches stored content" if ok else "dataset missing or corrupted",
                    observation=(
                        f"dataset {ds.name!r} re-hashes to its declared BOM digest"
                        if ok
                        else f"dataset {ds.name!r} missing/corrupted: declared {ds.digest[:16]}… recomputed {actual_digest[:16] or 'N/A'}…"
                    ),
                    evidence=[Evidence(
                        "artifact_store", "crypto",
                        {
                            "declared_digest": ds.digest,
                            "recomputed_digest": actual_digest,
                            "bytes": len(stored) if stored is not None else 0,
                        },
                        description="SHA3-256 recomputation of stored dataset bytes",
                    )],
                    confidence=1.0,
                    recommendation="QUARANTINE" if not ok else "",
                )
            )
        for prep in bom.by_kind("preprocessing"):
            ok = self.artifacts.verify(prep.digest)
            findings.append(
                make_finding(
                    f"preprocessing_integrity:{prep.name}",
                    ok,
                    "HIGH" if not ok else "LOW",
                    "" if ok else "preprocessing artifact missing or corrupted",
                    observation=(
                        f"preprocessing step {prep.name!r} verified"
                        if ok
                        else f"preprocessing step {prep.name!r} failed integrity check"
                    ),
                    evidence=[Evidence(
                        "artifact_store", "crypto",
                        {"declared_digest": prep.digest},
                    )],
                    confidence=1.0,
                    recommendation="ESCALATE" if not ok else "",
                )
            )
        # Derive the recommendation from the worst failing severity so a HIGH
        # finding can never be silently downgraded to ACCEPT (fail-closed).
        # CRITICAL dataset/preprocessing corruption quarantines; any other
        # failed integrity check escalates for human review; only a fully
        # clean sweep is ACCEPT. UNAVAILABLE evidence stays honest because the
        # findings that encode it (e.g. missing datasets) carry HIGH severity.
        _SEV_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
        failed = [f for f in findings if not f.passed]
        if not failed:
            rec = "ACCEPT"
        else:
            worst = max(
                (f.severity for f in failed if f.severity in _SEV_ORDER),
                key=lambda s: _SEV_ORDER[s],
                default="HIGH",
            )
            rec = "QUARANTINE" if worst == "CRITICAL" else "ESCALATE"
        return Observation(
            agent=self.name,
            subject_id=context.get("subject_id", ""),
            recommendation=rec,
            findings=findings,
            notes=f"checked {len(datasets)} dataset(s), "
            f"{len(bom.by_kind('preprocessing'))} preprocessing step(s)",
        )

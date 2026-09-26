"""Isolated hosted-path tenants for research experiments.

Each ``scratch_tenant`` is a fresh SQLite database under a caller-owned
scratch directory with one organization, one analyst, one entity and one
open assessment, using the production tenancy, submission, audit and
analysis-execution services. Nothing here reads configured SaaS
databases, production storage or demo fixtures.
"""

from __future__ import annotations

import io
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PERIOD_START = 1735689600.0  # satsa.analysis.synth.PERIOD_START
PERIOD_END = 1738281600.0  # satsa.analysis.synth.PERIOD_END
CSV_CATEGORIES = (
    "alerts",
    "cases",
    "investigation_steps",
    "escalations",
    "dispositions",
    "assets",
)


@dataclass
class HostedTenant:
    root: Path
    engine: Any
    organization_id: str
    analyst_id: str
    entity_id: str
    assessment_id: str
    audit: Any
    submissions: Any
    key_dir: Path

    def _identity(self, identity: str, name: str) -> None:
        now = time.time()
        self.engine.execute(
            "INSERT INTO identities (identity_id,kind,name,owner,status,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (identity, "human", name, "research", "active", now, now),
        )

    def submit(
        self, files: dict[str, bytes], *, key: str = "research"
    ) -> tuple[str, dict[str, Any], list[str]]:
        """Upload one CSV per category, complete, validate; return version."""
        submission_id = self.submissions.create_submission(
            self.assessment_id, idempotency_key=f"{key}-submission"
        )
        version_id = self.submissions.create_version(
            submission_id, idempotency_key=f"{key}-version"
        )
        uploaded: list[str] = []
        for category in CSV_CATEGORIES:
            data = files.get(category)
            if data is None:
                continue
            self.submissions.upload(
                version_id,
                category=category,
                stream=io.BytesIO(data),
                filename=f"{category}.csv",
                content_type="text/csv",
                idempotency_key=f"{key}-{category}",
            )
            uploaded.append(category)
        self.submissions.complete_uploads(version_id)
        return version_id, self.submissions.validate(version_id), uploaded

    def analyst_service(self):
        from satsa.analysis.execution import AnalysisExecutionService

        return AnalysisExecutionService(
            self.engine, self.organization_id, self.analyst_id, audit=self.audit
        )

    def supervisor_service(self):
        from satsa.analysis.execution import AnalysisExecutionService
        from satsa.tenancy import TenantAdministration

        identity = "research-supervisor"
        existing = self.engine.query_one(
            "SELECT id FROM satsa_users WHERE identity_id=?", (identity,)
        )
        if existing is None:
            self._identity(identity, "Research supervisor")
            admin = TenantAdministration(self.engine)
            user_id = admin.create_user(identity, "supervisor@example.test")
            admin.add_membership(self.organization_id, user_id, "satsa_supervisor")
        else:
            user_id = existing["id"]
        return AnalysisExecutionService(
            self.engine, self.organization_id, user_id, audit=self.audit
        )

    def worker(self, worker_id: str):
        from satsa.analysis.execution import AnalysisExecutionWorker

        return AnalysisExecutionWorker(
            self.engine,
            worker_id=worker_id,
            audit=self.audit,
            trust_key_dir=str(self.key_dir),
        )


def catalog_fixture(scenario: str) -> Any:
    """Build one catalog scenario fixture (``SCENARIO_MAP`` is untyped)."""
    from collections.abc import Callable
    from typing import cast

    from satsa.analysis.compval import SCENARIO_MAP

    builder = cast(Callable[[], tuple[Any, Any]], SCENARIO_MAP[scenario])
    return builder()[0]


def cse_csv_files(cse) -> dict[str, bytes]:
    """Serialize a synthetic ``_CSE`` with the existing CSV writer.

    Categories with no rows are omitted (not uploaded as header-only files).
    """
    import tempfile

    from satsa.analysis.synth import _write_cse

    fields = {
        "alerts": cse.alerts,
        "cases": cse.cases,
        "investigation_steps": cse.steps,
        "escalations": cse.escalations,
        "dispositions": cse.dispositions,
        "assets": cse.assets,
    }
    with tempfile.TemporaryDirectory(prefix="satsa-research-csv-") as temporary:
        directory = Path(temporary)
        _write_cse(cse, directory)
        return {
            category: (directory / f"{category}.csv").read_bytes()
            for category, rows in fields.items()
            if rows
        }


@contextmanager
def scratch_tenant(
    root: Path,
    *,
    entity_name: str = "Research entity",
    sector: str = "defence",
    key_dir: Path | None = None,
) -> Iterator[HostedTenant]:
    """Create one isolated tenant; the database is closed on exit.

    ``key_dir`` lets repeated trials share one scratch signing key, as a
    deployment does, so key generation is not billed to every trial.
    """
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    from qsmlops.evidence.ledger import EvidenceLedger
    from qsmlops.security.audit.service import AuditService
    from satsa.submissions import LocalArtifactStorage, SubmissionService
    from satsa.tenancy import TenantAdministration, TenantRepository

    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    engine = SQLiteDatabaseEngine(root / "research.sqlite3")
    engine.connect()
    try:
        MigrationRunner(engine).migrate()
        admin = TenantAdministration(engine)
        organization_id = admin.create_organization("Research synthetic tenant")
        now = time.time()
        engine.execute(
            "INSERT INTO identities (identity_id,kind,name,owner,status,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (
                "research-analyst",
                "human",
                "Research analyst",
                "research",
                "active",
                now,
                now,
            ),
        )
        analyst_id = admin.create_user("research-analyst", "analyst@example.test")
        admin.add_membership(organization_id, analyst_id, "satsa_analyst")
        tenant = TenantRepository(engine, organization_id, analyst_id)
        entity_id = tenant.create_entity(entity_name, sector=sector)
        assessment_id = tenant.create_assessment(entity_id, PERIOD_START, PERIOD_END)
        audit = AuditService(EvidenceLedger(root / "audit.jsonl"), database=engine)
        submissions = SubmissionService(
            engine,
            organization_id,
            analyst_id,
            storage=LocalArtifactStorage(root / "artifacts"),
            audit=audit,
        )
        yield HostedTenant(
            root=root,
            engine=engine,
            organization_id=organization_id,
            analyst_id=analyst_id,
            entity_id=entity_id,
            assessment_id=assessment_id,
            audit=audit,
            submissions=submissions,
            key_dir=Path(key_dir) if key_dir is not None else root / "signing-keys",
        )
    finally:
        engine.close()

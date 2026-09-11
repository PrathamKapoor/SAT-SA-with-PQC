"""Database service layer: engine + migrations + repository access.

one stop for the platform's SQL state. Instantiate with Settings (or a URL);
the service applies migrations lazily on first use. Migrations are dialect-
neutral so the same flow works if the engine is swapped for the production
quantum-safe database adapter.
"""
from __future__ import annotations

from qsmlops.core.settings import Settings
from qsmlops.database.engine import DatabaseEngine, create_engine
from qsmlops.database.migrations import MigrationRunner
from qsmlops.database.repositories import AuditEventRepository, IdentityRepository


class DatabaseService:
    def __init__(self, settings: Settings | str) -> None:
        if isinstance(settings, str):
            self._url = settings
        else:
            self._url = settings.database.url
        self._engine: DatabaseEngine | None = None
        self._migrated = False

    # -------------------- engine --------------------
    @property
    def engine(self) -> DatabaseEngine:
        if self._engine is None:
            self._engine = create_engine(self._url)
        return self._engine

    @property
    def dialect(self) -> str:
        return self.engine.dialect

    def migrate(self) -> list[str]:
        """Apply pending schema migrations; returns names applied."""
        applied = MigrationRunner(self.engine).migrate()
        self._migrated = True
        return applied

    def ensure_ready(self) -> None:
        if not self._migrated:
            self.migrate()

    @property
    def url(self) -> str:
        return self._url

    # -------------------- repositories --------------------
    def identities(self) -> IdentityRepository:
        self.ensure_ready()
        return IdentityRepository(self.engine)

    def audit_events(self) -> AuditEventRepository:
        self.ensure_ready()
        return AuditEventRepository(self.engine)

    # -------------------- misc --------------------
    def close(self) -> None:
        if self._engine is not None:
            self._engine.close()
            self._engine = None
            self._migrated = False

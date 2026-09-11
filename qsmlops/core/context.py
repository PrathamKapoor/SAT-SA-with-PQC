"""Service container: wiring and lifecycle for platform subsystems.

:class:`ServiceContainer` owns singletons and builds the dependency graph in
one place (ledger, keystore, artifact store, registry, agents, supervisor,
database, audit service, identity service, platform config). It is the single
composition root that the application factory, CLI entry points and tests
resolve services through.

Services use keyword-only names so call sites document the dependency.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from qsmlops.core.errors import ServiceUnavailableError
from qsmlops.core.settings import Settings


class ServiceContainer:
    """Library of lazily constructed singletons."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._providers: dict[str, Callable[[], Any]] = {}
        self._instances: dict[str, Any] = {}
        self._register_defaults()
    # -------------------- registration --------------------
    def register(self, name: str, provider: Callable[[], Any], *, replace: bool = False) -> None:
        if name in self._providers and not replace:
            raise ValueError(f"service {name!r} already registered")
        self._providers[name] = provider
        self._instances.pop(name, None)

    def get(self, name: str) -> Any:
        if name in self._instances:
            return self._instances[name]
        provider = self._providers.get(name)
        if provider is None:
            raise ServiceUnavailableError(f"unknown service {name!r}")
        instance = provider()
        self._instances[name] = instance
        return instance

    def has(self, name: str) -> bool:
        return name in self._providers or name in self._instances

    def set_instance(self, name: str, instance: Any) -> None:
        self._instances[name] = instance

    # -------------------- lifecycle --------------------
    def initialize(self) -> None:
        """Eagerly build everything the platform needs to operate."""
        self.settings.ensure_dirs()
        for name in (
            "logging",
            "ledger",
            "keystore",
            "artifacts",
            "registry",
            "database",
            "evidence_store",
            "audit_service",
            "identity_service",
            "agents",
            "supervisor",
            "pipeline",
        ):
            self.get(name)

    def close(self) -> None:
        for name in ("registry", "database"):
            inst = self._instances.get(name)
            if inst is not None and hasattr(inst, "close"):
                inst.close()
        self._instances.clear()

    # -------------------- default wiring --------------------
    def _register_defaults(self) -> None:
        from qsmlops.config import PlatformConfig

        settings = self.settings

        def _logging():
            from qsmlops.core.logging import configure_logging

            return configure_logging(settings.log_level, json_format=settings.json_logs)

        def _platform_config() -> PlatformConfig:
            # Phase 2: forward the layered crypto settings so the pipeline's
            # AgilityEngine default matches what configs/settings.*.yaml (or
            # QSMLOPS_ env vars / explicit overrides) actually declares —
            # previously only `home` crossed this boundary and the declared
            # algorithm had no effect on the running suite.
            return PlatformConfig(
                settings.home,
                default_signature_algorithm=settings.crypto.default_signature_algorithm,
                default_kem_algorithm=settings.crypto.default_key_encryption_algorithm,
            )

        def _pipeline():
            from qsmlops.pipeline.selfheal import SelfHealingMLOps

            return SelfHealingMLOps(self.get("platform_config"))

        # Shared state lives inside the pipeline instance; the container
        # surfaces the same object under stable service names.
        def _ledger():
            return self.get("pipeline").ledger

        def _keystore():
            return self.get("pipeline").keystore

        def _artifacts():
            return self.get("pipeline").artifacts

        def _registry():
            return self.get("pipeline").registry

        def _agents():
            return list(self.get("pipeline").agents)

        def _supervisor():
            return self.get("pipeline").supervisor

        def _database():
            from qsmlops.database.service import DatabaseService

            return DatabaseService(settings)

        def _evidence_store():
            from qsmlops.database.evidence_store import EvidenceStore

            return EvidenceStore(self.get("database"))

        def _audit_service():
            from qsmlops.security.audit.service import AuditService

            return AuditService(
                ledger=self.get("ledger"),
                database=self.get("database"),
            )

        def _identity_service():
            from qsmlops.security.identity.service import IdentityService

            # Phase 2: reuse the pipeline's already-configured AgilityEngine
            # instead of letting IdentityService construct its own with no
            # configuration — otherwise the two independently defaulted to
            # potentially different suites.
            return IdentityService(
                database=self.get("database"),
                audit=self.get("audit_service"),
                agility=self.get("pipeline").agility,
            )

        self.register("logging", _logging)
        self.register("platform_config", _platform_config)
        self.register("ledger", _ledger)
        self.register("keystore", _keystore)
        self.register("artifacts", _artifacts)
        self.register("registry", _registry)
        self.register("database", _database)
        self.register("evidence_store", _evidence_store)
        self.register("audit_service", _audit_service)
        self.register("identity_service", _identity_service)
        self.register("agents", _agents)
        self.register("supervisor", _supervisor)
        self.register("pipeline", _pipeline)

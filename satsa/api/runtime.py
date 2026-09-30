"""Shared, fail-closed runtime configuration and service wiring."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from qsmlops.database.engine import create_engine
from qsmlops.database.migrations import MigrationRunner
from qsmlops.evidence.ledger import EvidenceLedger
from qsmlops.security.audit.service import AuditService
from qsmlops.security.identity.service import IdentityService
from satsa.submissions.storage import (
    ArtifactStorage,
    LocalArtifactStorage,
    S3ArtifactStorage,
)


class RuntimeConfigurationError(ValueError):
    """A deployment environment is incomplete or unsafe for its selected mode."""


def _boolean(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = env.get(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value not in {"true", "false"}:
        raise RuntimeConfigurationError(f"{name} must be true or false")
    return value == "true"


@dataclass(frozen=True)
class RuntimeSettings:
    environment: str
    database_url: str
    storage_backend: str
    auto_migrate: bool
    data_dir: Path
    ledger_path: Path
    trust_key_dir: Path
    artifacts_dir: Path
    s3_bucket: str
    s3_endpoint_url: str | None
    s3_region: str
    s3_prefix: str
    s3_access_key: str | None
    s3_secret_key: str | None
    s3_use_ssl: bool
    s3_addressing_style: str
    db_pool_min_size: int
    db_pool_max_size: int
    db_connect_timeout: int
    db_pool_timeout: int
    db_statement_timeout_ms: int

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        require_trust_key: bool = True,
    ) -> RuntimeSettings:
        """Read and validate the deployment environment.

        ``require_trust_key`` is False only for the migration job, which runs
        before the signing key is provisioned and never signs anything.
        """
        env = os.environ if environ is None else environ
        mode = env.get("SATSA_ENVIRONMENT", "development").strip().lower()
        if mode not in {"development", "test", "production"}:
            raise RuntimeConfigurationError(
                "SATSA_ENVIRONMENT must be development, test, or production"
            )

        data_dir = Path(env.get("SATSA_DATA_DIR", ".satsa-api")).resolve()
        database_url = env.get("SATSA_DATABASE_URL") or env.get("QSMLOPS_DB_URL")
        if not database_url:
            if mode == "production":
                raise RuntimeConfigurationError(
                    "SATSA_DATABASE_URL must explicitly select PostgreSQL in production"
                )
            database_path = Path(
                env.get("SATSA_DB", str(data_dir / "satsa.db"))
            ).resolve()
            database_url = f"sqlite:///{database_path.as_posix()}"

        bucket = env.get("SATSA_S3_BUCKET", "").strip()
        backend = env.get("SATSA_STORAGE_BACKEND", "s3" if bucket else "local").lower()
        if backend not in {"local", "s3"}:
            raise RuntimeConfigurationError("SATSA_STORAGE_BACKEND must be local or s3")
        if backend == "s3" and not bucket:
            raise RuntimeConfigurationError(
                "SATSA_S3_BUCKET is required for S3 storage"
            )
        if backend == "local" and bucket:
            raise RuntimeConfigurationError(
                "SATSA_S3_BUCKET cannot be set while SATSA_STORAGE_BACKEND=local"
            )

        endpoint = env.get("SATSA_S3_ENDPOINT_URL", "").strip() or None
        access_key = env.get("SATSA_S3_ACCESS_KEY") or None
        secret_key = env.get("SATSA_S3_SECRET_KEY") or None
        if bool(access_key) != bool(secret_key):
            raise RuntimeConfigurationError(
                "SATSA_S3_ACCESS_KEY and SATSA_S3_SECRET_KEY must be set together"
            )
        legacy_path_style = _boolean(env, "SATSA_S3_PATH_STYLE", True)
        style = (
            env.get(
                "SATSA_S3_ADDRESSING_STYLE", "path" if legacy_path_style else "virtual"
            )
            .strip()
            .lower()
        )
        if style not in {"auto", "path", "virtual"}:
            raise RuntimeConfigurationError(
                "SATSA_S3_ADDRESSING_STYLE must be auto, path, or virtual"
            )
        use_ssl = _boolean(
            env, "SATSA_S3_USE_SSL", endpoint is None or endpoint.startswith("https://")
        )

        key_dir_raw = env.get("SATSA_TRUST_KEY_DIR")
        if mode == "production" and not key_dir_raw:
            raise RuntimeConfigurationError(
                "SATSA_TRUST_KEY_DIR must point to provisioned durable key material"
            )
        key_dir = Path(key_dir_raw or str(data_dir / "keys")).resolve()
        ledger_raw = env.get("SATSA_LEDGER_PATH")
        if mode == "production" and not ledger_raw:
            raise RuntimeConfigurationError(
                "SATSA_LEDGER_PATH must identify durable shared ledger storage"
            )
        ledger_path = Path(
            ledger_raw or str(data_dir / "evidence-ledger.jsonl")
        ).resolve()
        artifacts_dir = Path(
            env.get("SATSA_ARTIFACTS_DIR", str(data_dir / "artifacts"))
        ).resolve()

        auto_migrate = _boolean(env, "SATSA_AUTO_MIGRATE", mode != "production")
        if mode == "production":
            if not database_url.startswith(("postgresql://", "postgres://")):
                raise RuntimeConfigurationError(
                    "production requires a PostgreSQL SATSA_DATABASE_URL"
                )
            if backend != "s3":
                raise RuntimeConfigurationError(
                    "production requires S3 object storage; local artifact storage is offline-only"
                )
            # A database on another host (RDS) is reached over the network:
            # the deployment asks for server-certificate verification, and a
            # URL that would silently skip it is refused.
            if _boolean(env, "SATSA_DB_REQUIRE_VERIFIED_TLS", False):
                from psycopg.conninfo import conninfo_to_dict

                params = conninfo_to_dict(database_url)
                if params.get("sslmode") != "verify-full" or not params.get("sslrootcert"):
                    raise RuntimeConfigurationError(
                        "SATSA_DB_REQUIRE_VERIFIED_TLS needs sslmode=verify-full and sslrootcert in SATSA_DATABASE_URL"
                    )
                if not Path(params["sslrootcert"]).is_file():
                    raise RuntimeConfigurationError(
                        "the database CA bundle named by sslrootcert is missing"
                    )
            if (
                require_trust_key
                and not key_dir.joinpath("satsa_trust_key.json").is_file()
            ):
                raise RuntimeConfigurationError(
                    "production TRUST-SAT signing key is missing from SATSA_TRUST_KEY_DIR"
                )
            if endpoint and not endpoint.startswith("https://"):
                raise RuntimeConfigurationError(
                    "production S3 endpoints must use HTTPS"
                )
            if not use_ssl:
                raise RuntimeConfigurationError(
                    "production requires TLS for S3 storage"
                )
            if auto_migrate:
                raise RuntimeConfigurationError(
                    "SATSA_AUTO_MIGRATE must be false in production; run the migration job"
                )

        minimum = int(env.get("SATSA_DB_POOL_MIN_SIZE", "1"))
        maximum = int(env.get("SATSA_DB_POOL_MAX_SIZE", "5"))
        connect_timeout = int(env.get("SATSA_DB_CONNECT_TIMEOUT_SECONDS", "5"))
        pool_timeout = int(env.get("SATSA_DB_POOL_TIMEOUT_SECONDS", "5"))
        statement_timeout = int(env.get("SATSA_DB_STATEMENT_TIMEOUT_MS", "60000"))
        if not 0 <= minimum <= maximum <= 50:
            raise RuntimeConfigurationError("invalid PostgreSQL pool size bounds")
        if connect_timeout < 1 or pool_timeout < 1 or statement_timeout < 1:
            raise RuntimeConfigurationError("database timeouts must be positive")

        return cls(
            environment=mode,
            database_url=database_url,
            storage_backend=backend,
            auto_migrate=auto_migrate,
            data_dir=data_dir,
            ledger_path=ledger_path,
            trust_key_dir=key_dir,
            artifacts_dir=artifacts_dir,
            s3_bucket=bucket,
            s3_endpoint_url=endpoint,
            s3_region=env.get("SATSA_S3_REGION", "us-east-1"),
            s3_prefix=env.get("SATSA_S3_PREFIX", ""),
            s3_access_key=access_key,
            s3_secret_key=secret_key,
            s3_use_ssl=use_ssl,
            s3_addressing_style=style,
            db_pool_min_size=minimum,
            db_pool_max_size=maximum,
            db_connect_timeout=connect_timeout,
            db_pool_timeout=pool_timeout,
            db_statement_timeout_ms=statement_timeout,
        )


def build_runtime(
    *, migrate: bool | None = None, settings: RuntimeSettings | None = None
):
    """Build shared API/worker services; production only checks schema state."""
    settings = settings or RuntimeSettings.from_env()
    apply_migrations = settings.auto_migrate if migrate is None else migrate
    if settings.environment == "production" and apply_migrations:
        raise RuntimeConfigurationError(
            "production migrations must run in the dedicated migration step"
        )
    engine = create_engine(
        settings.database_url,
        pool_min_size=settings.db_pool_min_size,
        pool_max_size=settings.db_pool_max_size,
        connect_timeout=settings.db_connect_timeout,
        pool_timeout=settings.db_pool_timeout,
        statement_timeout_ms=settings.db_statement_timeout_ms,
    )
    try:
        migrations = MigrationRunner(engine)
        if apply_migrations:
            migrations.migrate()
        elif not migrations.status()["is_current"]:
            raise RuntimeConfigurationError(
                "database schema is not current; run `python -m satsa.api.migrate upgrade`"
            )

        if settings.environment == "production":
            from satsa.analysis.trust import TrustService

            trust = TrustService(
                engine, settings.trust_key_dir, organization_id="runtime-key-check"
            )
            trust.validate_signing_key()

        if settings.environment != "production":
            settings.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            settings.trust_key_dir.mkdir(parents=True, exist_ok=True)
            if settings.storage_backend == "local":
                settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
        audit = AuditService(EvidenceLedger(settings.ledger_path), database=engine)
        identity = IdentityService(
            engine,
            AuditService(
                EvidenceLedger(
                    settings.ledger_path.parent / "identity-audit-ledger.jsonl"
                ),
                database=engine,
            ),
        )
        if settings.storage_backend == "s3":
            import boto3
            from botocore.config import Config

            client_kwargs = {
                "service_name": "s3",
                "endpoint_url": settings.s3_endpoint_url,
                "region_name": settings.s3_region,
                "use_ssl": settings.s3_use_ssl,
                "config": Config(
                    s3={"addressing_style": settings.s3_addressing_style},
                    connect_timeout=settings.db_connect_timeout,
                    read_timeout=60,
                    retries={"max_attempts": 3, "mode": "standard"},
                ),
            }
            if settings.s3_access_key:
                client_kwargs["aws_access_key_id"] = settings.s3_access_key
                client_kwargs["aws_secret_access_key"] = settings.s3_secret_key
            client = boto3.client(**client_kwargs)
            storage: ArtifactStorage = S3ArtifactStorage(
                bucket=settings.s3_bucket, prefix=settings.s3_prefix, client=client
            )
        else:
            storage = LocalArtifactStorage(settings.artifacts_dir)
        return engine, audit, identity, storage, settings.trust_key_dir
    except BaseException:
        engine.close()
        raise

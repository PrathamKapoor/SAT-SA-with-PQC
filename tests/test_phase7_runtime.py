import pytest

from qsmlops.core.errors import StorageError
from satsa.api.runtime import RuntimeConfigurationError, RuntimeSettings
from satsa.api.settings import ApiSettings


def _production_env(tmp_path):
    key_dir = tmp_path / "keys"
    key_dir.mkdir(exist_ok=True)
    (key_dir / "satsa_trust_key.json").write_text(
        "provisioned test key", encoding="utf-8"
    )
    return {
        "SATSA_ENVIRONMENT": "production",
        "SATSA_DATABASE_URL": "postgresql://satsa:secret@db:5432/satsa",
        "SATSA_STORAGE_BACKEND": "s3",
        "SATSA_S3_BUCKET": "satsa-private",
        "SATSA_S3_ENDPOINT_URL": "https://objects.example.test",
        "SATSA_TRUST_KEY_DIR": str(key_dir),
        "SATSA_LEDGER_PATH": str(tmp_path / "durable" / "ledger.jsonl"),
        "SATSA_ALLOWED_HOSTS": "api.example.test",
        "SATSA_COOKIE_SECURE": "true",
        "SATSA_AUTO_MIGRATE": "false",
    }


def test_production_requires_postgres_private_storage_and_provisioned_key(tmp_path):
    env = _production_env(tmp_path)
    del env["SATSA_S3_BUCKET"]
    with pytest.raises(RuntimeConfigurationError, match="SATSA_S3_BUCKET"):
        RuntimeSettings.from_env(env)


def test_production_rejects_sqlite_and_local_artifacts(tmp_path):
    env = _production_env(tmp_path)
    env["SATSA_DATABASE_URL"] = "sqlite:///local.db"
    with pytest.raises(RuntimeConfigurationError, match="PostgreSQL"):
        RuntimeSettings.from_env(env)

    env = _production_env(tmp_path)
    env["SATSA_STORAGE_BACKEND"] = "local"
    with pytest.raises(RuntimeConfigurationError, match="S3"):
        RuntimeSettings.from_env(env)


def test_production_requires_migrations_to_run_as_an_explicit_step(tmp_path):
    env = _production_env(tmp_path)
    env["SATSA_AUTO_MIGRATE"] = "true"
    with pytest.raises(RuntimeConfigurationError, match="SATSA_AUTO_MIGRATE"):
        RuntimeSettings.from_env(env)


def test_development_mode_keeps_explicit_sqlite_offline_default(tmp_path):
    settings = RuntimeSettings.from_env({"SATSA_DATA_DIR": str(tmp_path)})
    assert settings.environment == "development"
    assert settings.database_url.startswith("sqlite:///")
    assert settings.storage_backend == "local"
    assert settings.auto_migrate is True


def test_shared_runtime_can_check_migrated_sqlite_without_auto_migration(tmp_path):
    from qsmlops.database.engine import create_engine
    from qsmlops.database.migrations import MigrationRunner
    from satsa.api.runtime import build_runtime

    db_path = tmp_path / "offline.db"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    MigrationRunner(engine).migrate()
    engine.close()
    settings = RuntimeSettings.from_env(
        {
            "SATSA_ENVIRONMENT": "development",
            "SATSA_DATABASE_URL": f"sqlite:///{db_path.as_posix()}",
            "SATSA_DATA_DIR": str(tmp_path / "runtime"),
            "SATSA_AUTO_MIGRATE": "false",
        }
    )
    runtime_engine, _audit, _identity, storage, _key_dir = build_runtime(
        settings=settings
    )
    try:
        assert runtime_engine.query_one("SELECT 1 AS ready") == {"ready": 1}
        storage.check_ready()
    finally:
        storage.close()
        runtime_engine.close()


def test_runtime_refuses_to_migrate_when_auto_migration_is_disabled(tmp_path):
    from satsa.api.runtime import build_runtime

    db_path = tmp_path / "unmigrated.db"
    settings = RuntimeSettings.from_env(
        {
            "SATSA_ENVIRONMENT": "development",
            "SATSA_DATABASE_URL": f"sqlite:///{db_path.as_posix()}",
            "SATSA_DATA_DIR": str(tmp_path / "runtime"),
            "SATSA_AUTO_MIGRATE": "false",
        }
    )
    with pytest.raises(RuntimeConfigurationError, match="schema is not current"):
        build_runtime(settings=settings)
    engine = SQLiteDatabaseEngine(db_path)
    try:
        assert (
            engine.query_one(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
            )
            is None
        )
    finally:
        engine.close()


def test_production_cookie_and_host_configuration_fails_closed(tmp_path):
    env = _production_env(tmp_path)
    env["SATSA_COOKIE_SECURE"] = "false"
    with pytest.raises(ValueError, match="secure"):
        ApiSettings.from_env(env)

    env = _production_env(tmp_path)
    env["SATSA_ALLOWED_HOSTS"] = "localhost"
    with pytest.raises(ValueError, match="production host"):
        ApiSettings.from_env(env)


def test_cookie_samesite_none_requires_secure_cookie():
    with pytest.raises(ValueError, match="SameSite=None"):
        ApiSettings(secure_cookies=False, cookie_samesite="none")

    settings = ApiSettings(secure_cookies=True, cookie_samesite="none")
    assert settings.cookie_samesite == "none"


def test_forwarded_headers_require_an_explicit_proxy_ip_allowlist(tmp_path):
    env = _production_env(tmp_path)
    env["SATSA_TRUST_PROXY_HEADERS"] = "true"
    with pytest.raises(ValueError, match="SATSA_TRUSTED_PROXIES"):
        ApiSettings.from_env(env)

    env["SATSA_TRUSTED_PROXIES"] = "10.8.0.0/16,192.0.2.10"
    settings = ApiSettings.from_env(env)
    assert settings.trust_proxy_headers is True
    assert settings.trusted_proxies == ("10.8.0.0/16", "192.0.2.10")

    env["SATSA_TRUSTED_PROXIES"] = "*"
    with pytest.raises(ValueError, match="wildcard"):
        ApiSettings.from_env(env)


from qsmlops.database.engine import SQLiteDatabaseEngine
from qsmlops.database.migrations import MIGRATIONS, Migration, MigrationRunner


def test_migration_status_distinguishes_fresh_behind_and_current_database(
    tmp_path, monkeypatch
):
    from qsmlops.database import migrations

    engine = SQLiteDatabaseEngine(tmp_path / "status.db")
    runner = MigrationRunner(engine)
    try:
        fresh = runner.status()
        assert fresh["current_version"] == 0
        assert fresh["target_version"] == max(m.version for m in MIGRATIONS)
        assert fresh["is_current"] is False
        assert fresh["pending_versions"] == [m.version for m in MIGRATIONS]
        assert (
            engine.query_one(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
            )
            is None
        )

        monkeypatch.setattr(migrations, "MIGRATIONS", MIGRATIONS[:-1])
        runner.migrate()
        monkeypatch.setattr(migrations, "MIGRATIONS", MIGRATIONS)
        behind = runner.status()
        assert behind["is_current"] is False
        assert behind["pending_versions"] == [MIGRATIONS[-1].version]
        runner.migrate()
        current = runner.status()
        assert current["current_version"] == current["target_version"]
        assert current["is_current"] is True
        assert current["pending_versions"] == []
    finally:
        engine.close()


def test_failed_sqlite_migration_does_not_record_or_leave_partial_schema(
    tmp_path, monkeypatch
):
    from qsmlops.database import migrations

    engine = SQLiteDatabaseEngine(tmp_path / "failed-migration.db")
    runner = MigrationRunner(engine)
    runner.migrate()
    baseline = runner.applied_versions()
    version = max(m.version for m in MIGRATIONS) + 1
    bad = Migration(
        version,
        "must_rollback",
        (
            "CREATE TABLE phase7_partial (id INTEGER PRIMARY KEY)",
            "THIS IS NOT SQL",
        ),
    )
    monkeypatch.setattr(migrations, "MIGRATIONS", MIGRATIONS + (bad,))
    try:
        with pytest.raises(StorageError):
            runner.migrate()
        assert runner.applied_versions() == baseline
        assert (
            engine.query_one(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='phase7_partial'"
            )
            is None
        )
    finally:
        engine.close()


def test_provisioned_trust_key_self_test_rejects_mismatched_keypair(tmp_path):
    import base64
    import json

    from qsmlops.crypto.providers import SIGNATURE_PROVIDERS
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from satsa.analysis.trust import TrustService

    engine = SQLiteDatabaseEngine(tmp_path / "key-check.db")
    key_dir = tmp_path / "keys"
    try:
        TrustService(engine, key_dir).validate_signing_key()
        data_path = key_dir / "satsa_trust_key.json"
        data = json.loads(data_path.read_text(encoding="utf-8"))
        other = SIGNATURE_PROVIDERS[data["algorithm_id"]].generate_keypair()
        data["public_key"] = base64.b64encode(other.public_key).decode("ascii")
        data_path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="key pair is invalid"):
            TrustService(engine, key_dir).validate_signing_key()
    finally:
        engine.close()

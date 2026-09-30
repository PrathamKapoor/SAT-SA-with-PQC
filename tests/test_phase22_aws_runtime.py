"""Phase 22: AWS runtime configuration (RDS over verified TLS, S3 via the instance role)."""

import pytest

from satsa.api.runtime import RuntimeConfigurationError, RuntimeSettings
from test_phase7_runtime import _production_env


def _aws_env(tmp_path, url_suffix="?sslmode=verify-full&sslrootcert={ca}"):
    ca = tmp_path / "rds-ca.pem"
    ca.write_text("-----BEGIN CERTIFICATE-----\n", encoding="utf-8")
    env = _production_env(tmp_path)
    env["SATSA_DATABASE_URL"] = (
        "postgresql://satsa:p%40ss@satsa.abc.ap-south-1.rds.amazonaws.com:5432/satsa"
        + url_suffix.format(ca=ca.as_posix())
    )
    env["SATSA_DB_REQUIRE_VERIFIED_TLS"] = "true"
    # Native AWS S3 through the EC2 role: no endpoint, no static keys.
    del env["SATSA_S3_ENDPOINT_URL"]
    env["SATSA_S3_REGION"] = "ap-south-1"
    return env


def test_rds_with_verified_tls_and_role_based_s3_is_accepted(tmp_path):
    settings = RuntimeSettings.from_env(_aws_env(tmp_path))
    assert settings.s3_endpoint_url is None
    assert settings.s3_access_key is None and settings.s3_secret_key is None
    assert settings.s3_region == "ap-south-1"
    assert settings.s3_use_ssl is True


@pytest.mark.parametrize("suffix", [
    "",
    "?sslmode=require",
    "?sslmode=verify-ca&sslrootcert={ca}",
    "?sslmode=verify-full",
    "?sslmode=disable",
])
def test_unverified_database_tls_is_refused(tmp_path, suffix):
    with pytest.raises(RuntimeConfigurationError, match="verify-full|sslrootcert"):
        RuntimeSettings.from_env(_aws_env(tmp_path, suffix))


def test_missing_ca_bundle_is_refused(tmp_path):
    env = _aws_env(tmp_path)
    env["SATSA_DATABASE_URL"] = env["SATSA_DATABASE_URL"].replace("rds-ca.pem", "absent.pem")
    with pytest.raises(RuntimeConfigurationError, match="CA bundle"):
        RuntimeSettings.from_env(env)


def test_guard_is_opt_in_for_the_bundled_database(tmp_path):
    env = _production_env(tmp_path)  # bundled container on the private network
    assert RuntimeSettings.from_env(env).database_url.startswith("postgresql://")

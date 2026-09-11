"""Configuration system: typed settings with environment separation.

Layered resolution order (later layers win):

    1. built-in defaults (per environment profile)
    2. ``{config_dir}/settings.{env}.yaml``   (if the file exists)
    3. environment variables (``QSMLOPS_``-prefixed)
    4. explicit overrides passed to :func:`load_settings`

Environments: ``development`` (default), ``testing``, ``production``.
The env is selected via ``QSMLOPS_ENV``. Production profiles fail closed on
debug flags and default to JSON logs; nothing else is magic — all values can
still be overridden.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qsmlops.core.errors import ConfigurationError

ENV_DEVELOPMENT = "development"
ENV_TESTING = "testing"
ENV_PRODUCTION = "production"
ENVIRONMENTS = (ENV_DEVELOPMENT, ENV_TESTING, ENV_PRODUCTION)

ENV_VAR = "QSMLOPS_ENV"


@dataclass
class ApiSettings:
    host: str = "127.0.0.1"
    port: int = 8000
    # Phase 2 (Part G): Host-header allowlist for starlette's
    # TrustedHostMiddleware. "*" (the default) preserves prior behaviour
    # exactly — no Host validation, matching every existing deployment.
    # An operator serving this on a shared network should set explicit
    # hostnames/IPs here; see docs/phase2/offline-hardening.md (Part G).
    trusted_hosts: list[str] = field(default_factory=lambda: ["*"])


@dataclass
class DatabaseSettings:
    """Connection descriptor. Only the SQLite dialect is implemented in
    Phase 1; the URL form keeps the door open for a quantum-safe or managed
    database in later phases without API changes."""

    url: str = ""


@dataclass
class CryptoSettings:
    default_signature_algorithm: str = "ML-DSA-65"
    default_key_encryption_algorithm: str = "ML-KEM-768"
    default_key_lifetime_days: float = 90.0
    vault_kdf_iterations: int = 600_000


@dataclass
class Settings:
    env: str = ENV_DEVELOPMENT
    home: Path = field(default_factory=lambda: Path.home() / ".qsmlops")
    debug: bool = False
    log_level: str = "INFO"
    json_logs: bool = False
    api: ApiSettings = field(default_factory=ApiSettings)
    database: DatabaseSettings = field(default_factory=DatabaseSettings)
    crypto: CryptoSettings = field(default_factory=CryptoSettings)
    source_files: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.env not in ENVIRONMENTS:
            raise ConfigurationError(
                f"unknown environment {self.env!r}; expected one of {ENVIRONMENTS}"
            )
        if isinstance(self.api, dict):
            self.api = ApiSettings(**self.api)
        if isinstance(self.database, dict):
            self.database = DatabaseSettings(**self.database)
        if isinstance(self.crypto, dict):
            self.crypto = CryptoSettings(**self.crypto)
        self.home = Path(self.home)
        if self.env == ENV_PRODUCTION and self.debug:
            raise ConfigurationError("debug mode is not allowed in production")
        if not self.database.url:
            self.database.url = f"sqlite:///{self.platform_dir / 'platform.sqlite3'}"

    # -------------------- derived layout --------------------
    @property
    def platform_dir(self) -> Path:
        return self.home / "platform"

    @property
    def artifacts_dir(self) -> Path:
        return self.home / "artifacts"

    @property
    def keys_dir(self) -> Path:
        return self.home / "keys"

    @property
    def ledger_path(self) -> Path:
        return self.home / "ledger" / "evidence.jsonl"

    @property
    def registry_db_path(self) -> Path:
        return self.home / "registry" / "registry.sqlite3"

    @property
    def learning_path(self) -> Path:
        return self.home / "supervisor" / "learning.json"

    @property
    def packet_store_path(self) -> Path:
        """Content-addressed packet bodies (F1) — co-located with ledger."""
        return self.ledger_path.parent / "packets"

    def ensure_dirs(self) -> None:
        for p in (
            self.platform_dir,
            self.artifacts_dir,
            self.keys_dir,
            self.ledger_path.parent,
            self.registry_db_path.parent,
            self.learning_path.parent,
            self.packet_store_path,
        ):
            p.mkdir(parents=True, exist_ok=True)

    def summary(self) -> dict[str, Any]:
        return {
            "env": self.env,
            "home": str(self.home),
            "debug": self.debug,
            "log_level": self.log_level,
            "json_logs": self.json_logs,
            "api_host": self.api.host,
            "api_port": self.api.port,
            "database_url": self.database.url,
            "default_signature_algorithm": self.crypto.default_signature_algorithm,
            "source_files": list(self.source_files),
        }


# -------------------- defaults per environment --------------------
_DEFAULT_OVERRIDES: dict[str, dict[str, Any]] = {
    ENV_DEVELOPMENT: {"log_level": "DEBUG", "json_logs": False},
    ENV_TESTING: {"log_level": "WARNING", "json_logs": False},
    ENV_PRODUCTION: {"log_level": "INFO", "json_logs": True},
}


def _defaults_for(env: str) -> dict[str, Any]:
    return dict(_DEFAULT_OVERRIDES[env])


# -------------------- env-var mapping --------------------
def _coerce(value: str, kind: type) -> Any:
    if kind is bool:
        return value.strip().lower() in ("1", "true", "yes", "on")
    if kind is int:
        return int(value)
    if kind is float:
        return float(value)
    return value


_ENV_MAP: dict[str, tuple[str, type]] = {
    "QSMLOPS_HOME": ("home", str),
    "QSMLOPS_DEBUG": ("debug", bool),
    "QSMLOPS_LOG_LEVEL": ("log_level", str),
    "QSMLOPS_JSON_LOGS": ("json_logs", bool),
    "QSMLOPS_API_HOST": ("api.host", str),
    "QSMLOPS_API_PORT": ("api.port", int),
    "QSMLOPS_DB_URL": ("database.url", str),
    "QSMLOPS_KEY_LIFETIME_DAYS": ("crypto.default_key_lifetime_days", float),
}


def _read_env_vars(environ: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for var, (key, kind) in _ENV_MAP.items():
        if var in environ:
            out[key] = _coerce(environ[var], kind)
    return out


def _set_nested(target: dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    node = target
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise ConfigurationError(f"cannot nest settings key {dotted_key!r}")
    node[parts[-1]] = value


def _deep_merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _flatten_env_vars(overrides: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in overrides.items():
        if isinstance(value, dict):
            for sub_key, sub_value in _flatten_env_vars(value).items():
                flat[f"{key}.{sub_key}"] = sub_value
        else:
            flat[key] = value
    return flat


def _apply_flat(doc: dict[str, Any], values: dict[str, Any], source: str) -> dict[str, Any]:
    for key, value in values.items():
        _set_nested(doc, key, value)
    env_value = doc.get("env")
    if env_value is not None and env_value not in ENVIRONMENTS:
        raise ConfigurationError(
            f"{source}: unknown environment {env_value!r}; expected one of {ENVIRONMENTS}"
        )
    if "home" in doc:
        doc["home"] = Path(doc["home"])
    return doc


def load_settings(
    env: str | None = None,
    *,
    config_dir: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
    environ: dict[str, str] | None = None,
) -> Settings:
    """Build Settings from defaults -> config file -> env vars -> overrides."""
    environ = environ if environ is not None else dict(os.environ)
    env = env or environ.get(ENV_VAR, ENV_DEVELOPMENT)
    if env not in ENVIRONMENTS:
        raise ConfigurationError(
            f"unknown environment {env!r}; expected one of {ENVIRONMENTS}"
        )
    doc = _defaults_for(env)
    doc["env"] = env

    source_files: list[str] = []
    if config_dir is None:
        config_dir = Path(__file__).parents[2] / "configs"
    config_file = Path(config_dir) / f"settings.{env}.yaml"
    if config_file.exists():
        try:
            import yaml
        except ImportError as exc:
            raise ConfigurationError(
                f"PyYAML is required to load {config_file}; install pyyaml"
            ) from exc
        try:
            file_doc = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise ConfigurationError(f"invalid YAML in {config_file}: {exc}") from exc
        if not isinstance(file_doc, dict):
            raise ConfigurationError(f"{config_file} must contain a mapping at top level")
        file_env = file_doc.get("env")
        if file_env is not None and file_env != env:
            raise ConfigurationError(
                f"{config_file} declares env={file_env!r} but {env!r} was requested"
            )
        doc = _apply_flat(doc, _flatten_env_vars(file_doc), str(config_file))
        source_files.append(str(config_file))

    doc = _apply_flat(doc, _read_env_vars(environ), "environment variables")
    doc = _apply_flat(doc, _flatten_env_vars(overrides or {}), "overrides")

    settings = Settings(**doc)
    settings.source_files = source_files
    return settings

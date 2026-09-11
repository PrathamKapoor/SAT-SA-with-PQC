"""Global configuration and shared enums for the platform."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PlatformConfig:
    """Runtime configuration. All paths default under a single root directory.

    ``default_signature_algorithm``/``default_kem_algorithm`` (Phase 2): the
    configured PQC suite, forwarded to :class:`~qsmlops.crypto.agility.AgilityEngine`
    so the layered ``configs/settings.*.yaml`` value is what actually gets
    selected at runtime, instead of the engine silently auto-selecting its own
    strongest-available suite. ``None`` (the default) preserves the prior
    auto-selection behaviour for callers that construct ``PlatformConfig``
    without an explicit crypto policy (most tests, the demo script, the CLI).
    """

    root: Path | None = field(default=None)
    default_signature_algorithm: str | None = field(default=None)
    default_kem_algorithm: str | None = field(default=None)

    def __post_init__(self) -> None:
        if self.root is None:
            self.root = Path(os.environ.get("QSMLOPS_HOME", Path.home() / ".qsmlops"))

    @property
    def artifacts_dir(self) -> Path:
        return self.root / "artifacts"

    @property
    def keys_dir(self) -> Path:
        return self.root / "keys"

    @property
    def ledger_path(self) -> Path:
        return self.root / "ledger" / "evidence.jsonl"

    @property
    def packet_store_path(self) -> Path:
        """Content-addressed packet bodies (F1) — co-located with ledger."""
        return self.ledger_path.parent / "packets"

    @property
    def registry_path(self) -> Path:
        return self.root / "registry" / "registry.sqlite3"

    @property
    def platform_db_path(self) -> Path:
        return self.root / "platform" / "platform.sqlite3"

    @property
    def telemetry_path(self) -> Path:
        return self.root / "monitoring" / "telemetry.jsonl"

    @property
    def learning_path(self) -> Path:
        return self.root / "supervisor" / "learning.json"

    @property
    def keystore_passphrase(self) -> str | None:
        """Passphrase enabling the encrypted keystore (Gate-D remediation).

        When ``QSMLOPS_KEYSTORE_PASSPHRASE`` is set, the platform opens its
        key store through :class:`~qsmlops.crypto.secure_keystore.EncryptedKeyStore`
        (AES-256-GCM vault; any legacy plaintext ``secret_keys.json`` is
        migrated into the vault and deleted). When unset, the legacy
        filesystem keystore is used unchanged for development compatibility.
        """
        return os.environ.get("QSMLOPS_KEYSTORE_PASSPHRASE") or None

    def ensure_dirs(self) -> None:
        for p in (
            self.artifacts_dir,
            self.keys_dir,
            self.ledger_path.parent,
            self.registry_path.parent,
            self.learning_path.parent,
            (self.root / "monitoring"),
            self.packet_store_path,
        ):
            p.mkdir(parents=True, exist_ok=True)


# Severity weights used by the supervisor risk scorer.
SEVERITY_WEIGHTS: dict[str, float] = {
    "CRITICAL": 25.0,
    "HIGH": 10.0,
    "MEDIUM": 4.0,
    "LOW": 1.0,
}

# Deployment gate thresholds (overridable per model via passport policy).
DEFAULT_METRIC_THRESHOLDS: dict[str, float] = {
    "min_r2": 0.80,
    "max_mse": 0.05,
}

# Key rotation policy: maximum age of a signing key before ROTATE_KEYS.
DEFAULT_KEY_MAX_AGE_DAYS = 90

# Trust decision thresholds (Phase 5). A composite trust score at or above
# "trusted" yields TRUSTED; at or above "conditional" (but below trusted)
# yields CONDITIONALLY_TRUSTED; below yields REVIEW_REQUIRED. Hard
# cryptographic failures always dominate as BLOCKED regardless of score.
DEFAULT_TRUST_THRESHOLDS: dict[str, float] = {
    "trusted": 90.0,
    "conditional": 70.0,
}

# Phase 7/8 monitoring configuration.
MONITORING_ROLLING_WINDOW = 10          # observations per rolling window
MONITORING_MIN_HISTORY = 3              # minimum history before baselines fire
DRIFT_BROAD_FEATURE_FRACTION = 0.5      # fraction of features that counts as broad

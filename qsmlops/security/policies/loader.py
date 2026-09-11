"""Dynamic organization policy sets bound to the supervisor's PolicyEngine.

Organization-level rule sets live outside the supervisor's built-in default
document and may be edited (or swapped) while the service is running. The
loader watches the policy file's fingerprint (size + mtime) and transparently
re-loads it on change; a malformed or invalid document never replaces the
last known-good engine, and the failure is reported through
:attr:`DynamicPolicySet.last_error` for operators.

Supported formats: JSON and YAML (chosen by file extension).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from qsmlops.supervisor.policy import PolicyEngine, PolicyError

DEFAULT_POLICY_FILENAME = "policies.json"

_LOAD_ERRORS = (OSError, ValueError, PolicyError)


def _fingerprint(path: Path) -> tuple[int, float]:
    stat = path.stat()
    return (stat.st_size, stat.st_mtime)


@dataclass
class DynamicPolicySet:
    """A policy file watched for changes; exposes a fresh PolicyEngine."""

    path: str | Path
    _engine: PolicyEngine | None = field(default=None, repr=False)
    _loaded_fingerprint: tuple[int, float] | None = field(default=None, repr=False)
    last_error: str = ""
    reload_count: int = 0

    @property
    def engine(self) -> PolicyEngine:
        """Current engine; re-loads the file first if it changed on disk.

        A broken document never takes effect: the last known-good engine
        keeps serving and ``last_error`` records why. Raises only when no
        good engine was ever loaded.
        """
        if self._engine is not None and not self._has_changed():
            return self._engine
        try:
            candidate = PolicyEngine.from_file(self.path)
        except _LOAD_ERRORS as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            if self._engine is None:
                raise
            return self._engine
        return self._install(candidate)

    def _has_changed(self) -> bool:
        try:
            return _fingerprint(Path(self.path)) != self._loaded_fingerprint
        except OSError:
            return False

    def _install(self, candidate: PolicyEngine) -> PolicyEngine:
        self._engine = candidate
        self._loaded_fingerprint = _fingerprint(Path(self.path))
        self.reload_count += 1
        self.last_error = ""
        return self._engine

    def reload(self) -> bool:
        """Force a re-load.

        Returns True when the installed rule set differs from the previous
        one; raises if the document cannot be loaded (availability is never
        silently degraded by a forced reload).
        """
        candidate = PolicyEngine.from_file(self.path)
        changed = (
            self._engine is None
            or candidate.to_dict() != self._engine.to_dict()
        )
        self._install(candidate)
        return changed


class PolicyRegistry:
    """Named registry of dynamic policy sets with hot-reload semantics."""

    def __init__(self, config_dir: str | Path | None = None) -> None:
        self.config_dir = Path(config_dir) if config_dir else None
        self._sets: dict[str, DynamicPolicySet] = {}

    def register(
        self,
        name: str,
        path: str | Path | None = None,
    ) -> DynamicPolicySet:
        if path is None:
            if self.config_dir is None:
                raise ValueError("no path given and no default config_dir configured")
            path = self.config_dir / DEFAULT_POLICY_FILENAME
        pset = DynamicPolicySet(path)
        pset.engine  # fail fast on a missing/broken initial file
        self._sets[name] = pset
        return pset

    def get(self, name: str) -> DynamicPolicySet:
        return self._sets[name]

    def engine_for(self, name: str) -> PolicyEngine:
        return self.get(name).engine


def write_default_document(path: str | Path, document: dict) -> Path:
    """Persist ``document`` as JSON at ``path`` (creates parent dirs)."""
    import json

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return p

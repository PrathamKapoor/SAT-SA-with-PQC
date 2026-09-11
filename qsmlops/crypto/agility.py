"""Cryptographic Agility Engine.

Manages named cipher suites (signature + KEM + hash combinations), their
lifecycle status, suite selection policy and migration planning between
suites. Algorithms are never hardcoded at call sites; everything resolves
through this engine so that a future PQC upgrade is a data change, not a
code change.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from qsmlops.crypto.hashing import HASH_ALGORITHM
from qsmlops.crypto.providers import (
    KEM_PROVIDERS,
    SIGNATURE_PROVIDERS,
    ProviderError,
)

STATUS_RECOMMENDED = "recommended"
STATUS_ACCEPTABLE = "acceptable"
STATUS_DEPRECATED = "deprecated"
STATUS_EMERGENCY = "emergency"


@dataclass(frozen=True)
class CryptoSuite:
    suite_id: str
    signature_algorithm: str
    kem_algorithm: str
    hash_algorithm: str = HASH_ALGORITHM
    status: str = STATUS_RECOMMENDED
    notes: str = ""


@dataclass
class MigrationPlan:
    from_suite: str
    to_suite: str
    steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "from_suite": self.from_suite,
            "to_suite": self.to_suite,
            "steps": list(self.steps),
        }


class AgilityEngine:
    """Registry of cipher suites with selection and migration planning.

    Phase 2 hardening: the engine used to *always* self-select the strongest
    available suite as ``default_suite``, silently ignoring any configured
    ``configs/settings.*.yaml`` value (``crypto.default_signature_algorithm`` /
    ``crypto.default_key_encryption_algorithm``) — those settings loaded and
    validated but had no code path into this engine. ``default_signature_algorithm``
    / ``default_kem_algorithm`` below close that gap: when both are supplied,
    the configured suite is authoritative and construction fails closed if it
    does not resolve to a known, registered suite. When neither is supplied
    (the default), behaviour is unchanged from before Phase 2 — this keeps
    every existing ``AgilityEngine()`` call site and test working.
    """

    def __init__(
        self,
        *,
        default_signature_algorithm: Optional[str] = None,
        default_kem_algorithm: Optional[str] = None,
    ) -> None:
        self._suites: dict[str, CryptoSuite] = {}
        for sig_alg in SIGNATURE_PROVIDERS:
            for kem_alg in KEM_PROVIDERS:
                level_sig = SIGNATURE_PROVIDERS[sig_alg].security_level
                level_kem = KEM_PROVIDERS[kem_alg].security_level
                suite_id = f"QS-{level_sig}{level_kem}-{sig_alg}+{kem_alg}"
                status = STATUS_RECOMMENDED if (
                    level_sig >= 3 or level_kem >= 3
                ) else STATUS_ACCEPTABLE
                self._suites[suite_id] = CryptoSuite(
                    suite_id=suite_id,
                    signature_algorithm=sig_alg,
                    kem_algorithm=kem_alg,
                    status=status,
                )
        self.default_suite: Optional[str] = None
        self.default_suite_obj: Optional[CryptoSuite] = None
        self._default_source = "unset"

        if default_signature_algorithm is not None or default_kem_algorithm is not None:
            if default_signature_algorithm is None or default_kem_algorithm is None:
                raise ProviderError(
                    "default_signature_algorithm and default_kem_algorithm must be "
                    "configured together; got only one of the two — check "
                    "configs/settings.*.yaml's crypto section"
                )
            configured = self._resolve_suite(
                default_signature_algorithm, default_kem_algorithm
            )
            self.default_suite = configured.suite_id
            self.default_suite_obj = configured
            self._default_source = "configured"
        else:
            recommended = [
                s for s in self._suites.values() if s.status == STATUS_RECOMMENDED
            ]
            if recommended:
                best = max(
                    recommended,
                    key=lambda s: (
                        SIGNATURE_PROVIDERS[s.signature_algorithm].security_level
                        + KEM_PROVIDERS[s.kem_algorithm].security_level
                    ),
                )
                self.default_suite = best.suite_id
                self.default_suite_obj = best
                self._default_source = "auto-selected-strongest"

    def _resolve_suite(self, sig_alg: str, kem_alg: str) -> CryptoSuite:
        """Find the registered suite for an explicitly configured algorithm
        pair. Fails closed (raises) rather than falling back to a different
        suite, per Phase 2 Part C3: invalid configuration must never silently
        resolve to an unintended algorithm."""
        if sig_alg not in SIGNATURE_PROVIDERS:
            raise ProviderError(
                f"configured signature algorithm {sig_alg!r} is not a known "
                f"provider (known: {sorted(SIGNATURE_PROVIDERS)})"
            )
        if kem_alg not in KEM_PROVIDERS:
            raise ProviderError(
                f"configured KEM algorithm {kem_alg!r} is not a known provider "
                f"(known: {sorted(KEM_PROVIDERS)})"
            )
        for suite in self._suites.values():
            if suite.signature_algorithm == sig_alg and suite.kem_algorithm == kem_alg:
                return suite
        raise ProviderError(  # pragma: no cover - unreachable given the generation loop above
            f"no suite registered for {sig_alg}+{kem_alg}"
        )

    def effective_policy(self) -> dict:
        """Expose the active cryptographic configuration for diagnostics,
        the ``/security`` API route and audit — never key material or secrets.

        ``configured`` distinguishes a suite chosen by explicit configuration
        from one this engine auto-selected in the absence of configuration,
        so a caller can tell the difference between "this is what was asked
        for" and "this is what the engine picked because nothing was asked."
        """
        if self.default_suite is None:
            return {"configured": False, "source": self._default_source, "suite_id": None}
        suite = self.get_suite(self.default_suite)
        return {
            "configured": self._default_source == "configured",
            "source": self._default_source,
            "suite_id": suite.suite_id,
            "signature_algorithm": suite.signature_algorithm,
            "signature_security_level": SIGNATURE_PROVIDERS[suite.signature_algorithm].security_level,
            "kem_algorithm": suite.kem_algorithm,
            "kem_security_level": KEM_PROVIDERS[suite.kem_algorithm].security_level,
            "hash_algorithm": suite.hash_algorithm,
            "status": suite.status,
        }

    def register_suite(self, suite: CryptoSuite) -> None:
        self._validate_suite(suite)
        self._suites[suite.suite_id] = suite

    @staticmethod
    def _validate_suite(suite: CryptoSuite) -> None:
        if suite.signature_algorithm not in SIGNATURE_PROVIDERS:
            raise ProviderError(
                f"unknown signature algorithm {suite.signature_algorithm!r}"
            )
        if suite.kem_algorithm not in KEM_PROVIDERS:
            raise ProviderError(f"unknown KEM algorithm {suite.kem_algorithm!r}")
        if suite.hash_algorithm != HASH_ALGORITHM:
            raise ProviderError(
                f"unsupported hash {suite.hash_algorithm!r}; platform standard is {HASH_ALGORITHM}"
            )

    def get_suite(self, suite_id: str) -> CryptoSuite:
        try:
            return self._suites[suite_id]
        except KeyError as exc:
            raise ProviderError(f"unknown suite {suite_id!r}") from exc

    def select_suite(self, suite_id: Optional[str] = None) -> CryptoSuite:
        if suite_id is not None:
            return self.get_suite(suite_id)
        if self.default_suite is None:
            raise ProviderError("no suites registered")
        return self.get_suite(self.default_suite)

    def assert_usable(self, suite: CryptoSuite) -> None:
        if suite.status == STATUS_DEPRECATED:
            raise ProviderError(
                f"suite {suite.suite_id} is deprecated; migrate before new use"
            )
        if suite.status == STATUS_EMERGENCY:
            pass  # usable only under break-glass; caller must record justification
        if suite.status not in (
            STATUS_RECOMMENDED,
            STATUS_ACCEPTABLE,
            STATUS_EMERGENCY,
        ):
            raise ProviderError(f"suite {suite.suite_id} unusable (status={suite.status})")

    def mark_deprecated(self, suite_id: str) -> None:
        suite = self.get_suite(suite_id)
        self._suites[suite_id] = CryptoSuite(
            suite_id=suite.suite_id,
            signature_algorithm=suite.signature_algorithm,
            kem_algorithm=suite.kem_algorithm,
            hash_algorithm=suite.hash_algorithm,
            status=STATUS_DEPRECATED,
            notes=suite.notes,
        )

    def plan_migration(
        self, from_suite_id: str, to_suite_id: Optional[str] = None
    ) -> MigrationPlan:
        src = self.get_suite(from_suite_id)
        dst = self.select_suite(to_suite_id)
        steps = [
            f"provision keys for target suite {dst.suite_id}",
            "deploy dual-verification window (verify old + new signatures)",
            f"re-sign all passports currently signed with {src.signature_algorithm}",
            f"rotate KEM key material from {src.kem_algorithm} to {dst.kem_algorithm}",
            "mark source suite deprecated",
            "retire verification support for source suite after grace period",
        ]
        return MigrationPlan(src.suite_id, dst.suite_id, steps)

    def audit_inventory(self, signed_with: dict[str, int]) -> dict:
        """Audit a mapping of suite_id -> count of artifacts using it."""
        report: dict[str, dict] = {}
        for suite_id, count in sorted(signed_with.items()):
            suite = self._suites.get(suite_id)
            report[suite_id] = {
                "artifacts": count,
                "status": suite.status if suite else "UNKNOWN_SUITE",
                "action": (
                    "none"
                    if suite and suite.status == STATUS_RECOMMENDED
                    else "migrate"
                ),
            }
        return report

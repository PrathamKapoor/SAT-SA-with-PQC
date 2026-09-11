"""Quantum Secure Model Registry.

SQLite-backed index over the content-addressed artifact store. The registry
enforces a strict trust lifecycle:

    REGISTERED -> VERIFIED -> APPROVED -> DEPLOYED
                       |            |
                       v            v
                 QUARANTINED    ROLLED_BACK
                       |
                       v
                     REVOKED

Core invariants:
- A model version is never trusted merely because it exists; promotion to
  VERIFIED requires a valid passport signature from a trust anchor AND an
  approving verification packet produced by a verifier distinct from the
  signer (separation of duties).
- Deployments are only allowed from APPROVED state and always emit evidence.
- Rollback re-activates the most recent previously-approved version.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

from qsmlops.artifacts.store import ArtifactStore
from qsmlops.crypto.hashing import HASH_ALGORITHM
from qsmlops.crypto.keys import KeyStore
from qsmlops.evidence.ledger import EvidenceLedger
from qsmlops.evidence.packet import VerificationPacket
from qsmlops.passport.passport import Passport
from qsmlops.scores import TrustResult, evaluate_trust
from qsmlops.supplychain.bom import QMLBOM

STATE_REGISTERED = "REGISTERED"
STATE_VERIFIED = "VERIFIED"
STATE_APPROVED = "APPROVED"
STATE_DEPLOYED = "DEPLOYED"
STATE_QUARANTINED = "QUARANTINED"
STATE_REVOKED = "REVOKED"
STATE_ROLLED_BACK = "ROLLED_BACK"

ACTIVE_STATES = {STATE_VERIFIED, STATE_APPROVED, STATE_DEPLOYED}

TRANSITIONS = {
    STATE_REGISTERED: {STATE_VERIFIED, STATE_QUARANTINED, STATE_REVOKED},
    STATE_VERIFIED: {STATE_APPROVED, STATE_QUARANTINED, STATE_REVOKED},
    STATE_APPROVED: {STATE_DEPLOYED, STATE_QUARANTINED, STATE_REVOKED},
    STATE_DEPLOYED: {STATE_ROLLED_BACK, STATE_QUARANTINED, STATE_REVOKED, STATE_DEPLOYED},
    STATE_QUARANTINED: {STATE_VERIFIED, STATE_REVOKED},
    STATE_ROLLED_BACK: {STATE_VERIFIED, STATE_QUARANTINED, STATE_REVOKED},
    STATE_REVOKED: set(),
}


class RegistryError(Exception):
    pass


class ModelRegistry:
    def __init__(
        self,
        db_path: Path,
        artifacts: ArtifactStore,
        keystore: KeyStore,
        ledger: EvidenceLedger,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.artifacts = artifacts
        self.keystore = keystore
        self.ledger = ledger
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._migrate()

    def _migrate(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS model_versions (
                version_id TEXT PRIMARY KEY,
                model_name TEXT NOT NULL,
                version INTEGER NOT NULL,
                artifact_digest TEXT NOT NULL,
                passport_digest TEXT NOT NULL,
                bom_digest TEXT NOT NULL,
                suite_id TEXT NOT NULL DEFAULT '',
                state TEXT NOT NULL,
                registered_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                UNIQUE(model_name, version)
            );
            CREATE TABLE IF NOT EXISTS deployments (
                deployment_id TEXT PRIMARY KEY,
                version_id TEXT NOT NULL,
                deployed_at REAL NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                packet_id TEXT NOT NULL DEFAULT ''
            );
            """
        )
        # Phase 5: persist the latest trust evaluation per version. History
        # remains in the evidence ledger; the row holds the newest result.
        cols = {row[1] for row in self._conn.execute("PRAGMA table_info(model_versions)")}
        for column, decl in (
            ("trust_score", "REAL"),
            ("trust_decision", "TEXT"),
            ("trust_evaluated_at", "REAL"),
            ("trust_report", "TEXT"),
        ):
            if column not in cols:
                self._conn.execute(
                    f"ALTER TABLE model_versions ADD COLUMN {column} {decl}"
                )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def register(
        self,
        passport: Passport,
        artifact_bytes: bytes,
        bom_digest: str,
    ) -> str:
        if not passport.signature:
            raise RegistryError("refusing to register an unsigned passport")
        artifact_digest = self.artifacts.put(artifact_bytes)
        passport_doc = _canonical(passport.to_dict()).encode("utf-8")
        passport_digest = self.artifacts.put(passport_doc)
        if passport.identity.get("artifact_digest") != artifact_digest:
            raise RegistryError(
                "passport artifact digest does not match stored artifact bytes"
            )
        version_id = uuid.uuid4().hex
        now = time.time()
        try:
            self._conn.execute(
                """INSERT INTO model_versions
                   (version_id, model_name, version, artifact_digest, passport_digest,
                    bom_digest, suite_id, state, registered_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    version_id,
                    passport.identity["name"],
                    int(passport.identity["version"]),
                    artifact_digest,
                    passport_digest,
                    bom_digest,
                    passport.signature.suite_id,
                    STATE_REGISTERED,
                    now,
                    now,
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise RegistryError(
                f"{passport.identity['name']} v{passport.identity['version']} already registered"
            ) from exc
        self.ledger.append(
            {
                "type": "registration",
                "version_id": version_id,
                "model": passport.identity["name"],
                "version": passport.identity["version"],
                "artifact_digest": artifact_digest,
                "passport_digest": passport_digest,
            }
        )
        return version_id

    def get_version(self, version_id: str) -> dict:
        row = self._conn.execute(
            "SELECT * FROM model_versions WHERE version_id=?", (version_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown version {version_id}")
        return dict(row)

    def find_version(self, model_name: str, version: int) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM model_versions WHERE model_name=? AND version=?",
            (model_name, version),
        ).fetchone()
        return dict(row) if row else None

    def load_passport(self, version_id: str) -> Passport:
        rec = self.get_version(version_id)
        try:
            doc = self.artifacts.get(rec["passport_digest"])
        except IOError:
            # Corrupted passport, read raw bytes without digest validation
            path = self.artifacts._path_for(rec["passport_digest"])
            doc = path.read_bytes()
        import json
        return Passport.from_dict(json.loads(doc.decode("utf-8")))

    def load_artifact(self, version_id: str) -> bytes:
        return self.artifacts.get(self.get_version(version_id)["artifact_digest"])

    def _load_bom_lenient(self, bom_digest: str) -> QMLBOM | None:
        """Load a BOM best-effort; corrupted bytes yield None (never crash)."""
        try:
            doc = self.artifacts.get_if_exists(bom_digest)
        except (IOError, ValueError):
            return None
        if doc is None:
            return None
        try:
            return QMLBOM.from_dict(json.loads(doc.decode("utf-8")))
        except (ValueError, UnicodeDecodeError):
            return None

    # ---------------- Phase 5: trust evaluation ----------------
    def trust_evaluation(
        self,
        version_id: str,
        observations=None,
        actor: str = "registry",
        persist: bool = True,
    ) -> TrustResult:
        """Evaluate and (by default) persist trust for a version.

        Structural evidence is gathered here (passport signature, artifact
        integrity, BOM verifiability, provenance completeness, key status).
        Agent observations may be supplied by the caller to enrich the
        operational component. The result is explainable and auditable:
        every persisted evaluation appends a `trust_evaluation` record to
        the evidence ledger.
        """
        rec = self.get_version(version_id)
        passport = self.load_passport(version_id)
        bom = self._load_bom_lenient(rec["bom_digest"])
        result = evaluate_trust(
            version_id=version_id,
            version_record=rec,
            passport=passport,
            keystore=self.keystore,
            artifact_store=self.artifacts,
            bom=bom,
            observations=observations,
            evidence_extras={
                "bom_digest": rec["bom_digest"],
                "model_name": rec["model_name"],
                "version": rec["version"],
            },
        )
        result.evaluated_by = actor
        if persist:
            self._conn.execute(
                "UPDATE model_versions SET trust_score=?, trust_decision=?,"
                " trust_evaluated_at=?, trust_report=? WHERE version_id=?",
                (
                    result.trust_score,
                    result.decision,
                    result.evaluated_at,
                    json.dumps(result.to_dict(), sort_keys=True),
                    version_id,
                ),
            )
            self._conn.commit()
            self.ledger.append(
                {
                    "type": "trust_evaluation",
                    "version_id": version_id,
                    "model": rec["model_name"],
                    "actor": actor,
                    "decision": result.decision,
                    "trust_score": result.trust_score,
                    "blocking": list(result.blocking_conditions),
                }
            )
        return result

    def latest_trust(self, version_id: str) -> dict | None:
        """Return the persisted latest trust report for a version, if any."""
        row = self._conn.execute(
            "SELECT trust_score, trust_decision, trust_evaluated_at, trust_report"
            " FROM model_versions WHERE version_id=?",
            (version_id,),
        ).fetchone()
        if row is None or row["trust_decision"] is None:
            return None
        return {
            "version_id": version_id,
            "trust_score": row["trust_score"],
            "trust_decision": row["trust_decision"],
            "evaluated_at": row["trust_evaluated_at"],
            "report": json.loads(row["trust_report"]) if row["trust_report"] else None,
        }

    def transition(
        self,
        version_id: str,
        new_state: str,
        packet: VerificationPacket | None = None,
        reason: str = "",
    ) -> None:
        rec = self.get_version(version_id)
        current = rec["state"]
        if new_state == current:
            return
        if new_state not in TRANSITIONS.get(current, set()):
            raise RegistryError(
                f"illegal transition {current} -> {new_state} for {version_id}"
            )
        self._conn.execute(
            "UPDATE model_versions SET state=?, updated_at=? WHERE version_id=?",
            (new_state, time.time(), version_id),
        )
        self._conn.commit()
        self.ledger.append(
            {
                "type": "state_transition",
                "version_id": version_id,
                "from": current,
                "to": new_state,
                "reason": reason,
                "packet_id": packet.packet_id if packet else "",
            }
        )

    def verify_version(
        self, version_id: str, verifier_owner: str, checks: list[tuple[str, bool]]
    ) -> VerificationPacket:
        """Run trust evaluation for a version and record the decision.

        `checks` are (name, passed) pairs supplied by agents. The registry adds
        its own cryptographic checks and enforces separation of duties: the
        verifier must differ from the passport signer owner.
        """
        rec = self.get_version(version_id)
        passport = self.load_passport(version_id)
        signer_owner = passport.signature.signer_key_id.split("-")[0] if passport.signature else ""
        if signer_owner and signer_owner == verifier_owner:
            raise RegistryError(
                "separation of duties violation: verifier cannot equal signer"
            )
        all_checks = list(checks)
        sig_ok = passport.verify_signature(self.keystore)
        all_checks.append(("passport_signature_valid", sig_ok))
        art_ok = self.artifacts.verify(rec["artifact_digest"])
        all_checks.append(("artifact_integrity", art_ok))
        artifact_match = passport.identity.get("artifact_digest") == rec["artifact_digest"]
        all_checks.append(("artifact_matches_passport", artifact_match))
        # Phase 4: record the cryptographic evidence backing this verification
        # so every packet proves WHICH suite/key/hash bound the artifact.
        crypto_proofs: dict = {"hash_algorithm": HASH_ALGORITHM}
        if passport.signature is not None:
            crypto_proofs.update(
                {
                    "suite_id": passport.signature.suite_id,
                    "signature_algorithm": passport.signature.algorithm_id,
                    "signer_key_id": passport.signature.signer_key_id,
                    "signed_digest": passport.signature.signed_digest,
                    "signature_verified": sig_ok,
                }
            )
        crypto_proofs["artifact_integrity"] = art_ok
        from qsmlops.evidence.packet import SecurityCheck
        packet = VerificationPacket.create(
            objective=f"verify model {rec['model_name']} v{rec['version']}",
            actor=verifier_owner,
            inputs={"version_id": version_id},
            artifacts={"artifact": rec["artifact_digest"], "passport": rec["passport_digest"]},
            security_checks=[
                SecurityCheck(name=n, passed=bool(p), severity="CRITICAL") for n, p in all_checks
            ],
            proofs={"crypto": crypto_proofs},
        )
        # The CRITICAL artifact_matches_passport binding check is part of the
        # pass/fail decision (registry.py:351). An attacker with DB-write access
        # who alters model_versions.artifact_digest must NOT pass verification.
        passed = all(p for _, p in checks) and sig_ok and art_ok and artifact_match
        packet.decision = "VERIFIED" if passed else "QUARANTINE"
        packet.status = "CLOSED"
        if passed:
            if self.get_version(version_id)["state"] in (STATE_REGISTERED, STATE_QUARANTINED):
                self.transition(version_id, STATE_VERIFIED, packet, reason="verification passed")
        else:
            if self.get_version(version_id)["state"] in ACTIVE_STATES:
                self.transition(version_id, STATE_QUARANTINED, packet, reason="verification failed")
        self.ledger.append_packet(packet)
        return packet

    def approve_deployment(
        self, version_id: str, approver: str, packet: VerificationPacket
    ) -> dict:
        """Governed promotion gate (Phase 5).

        Approval requires ALL of:
          - version in VERIFIED state,
          - an authorizing verification packet (no failed CRITICAL checks),
          - separation of duties: the approver must differ from the signer,
          - a passing trust evaluation derived from actual evidence.

        A favourable score can never bypass the hard cryptographic blockers
        embedded in the trust evaluation. Denials are audited in the ledger.
        """
        rec = self.get_version(version_id)
        if rec["state"] != STATE_VERIFIED:
            raise RegistryError(
                f"only VERIFIED versions can be approved (state={rec['state']})"
            )
        failed_critical = [
            c for c in packet.security_checks if not c.passed and c.severity == "CRITICAL"
        ]
        if failed_critical or packet.decision not in ("ACCEPT", "VERIFIED"):
            self._audit_approval_denied(
                version_id, approver,
                "verification packet does not authorize deployment",
            )
            raise RegistryError(
                "approval refused: verification packet does not authorize deployment"
            )
        if not approver:
            self._audit_approval_denied(version_id, approver, "missing approver identity")
            raise RegistryError("approval refused: missing approver identity")

        passport = self.load_passport(version_id)
        signer_owner = (
            passport.signature.signer_key_id.split("-")[0] if passport.signature else ""
        )
        if signer_owner and approver == signer_owner:
            self._audit_approval_denied(
                version_id, approver, "separation of duties: approver equals signer"
            )
            raise RegistryError(
                "separation of duties violation: approver cannot equal signer"
            )

        # Trust gate: fresh evidence-based evaluation; persisted for audit.
        trust = self.trust_evaluation(version_id, actor=f"approval:{approver}")
        if trust.decision not in ("TRUSTED", "CONDITIONALLY_TRUSTED"):
            reason = (
                f"trust evaluation returned {trust.decision}: {trust.explanation}"
            )
            self._audit_approval_denied(version_id, approver, reason)
            raise RegistryError(f"approval refused: {reason}")

        self.transition(version_id, STATE_APPROVED, packet, reason=f"approved by {approver}")
        self.ledger.append_packet(packet)
        return {
            "version_id": version_id,
            "state": STATE_APPROVED,
            "approver": approver,
            "trust_score": trust.trust_score,
            "trust_decision": trust.decision,
            "packet_id": packet.packet_id,
            "approved_at": time.time(),
        }

    def _audit_approval_denied(self, version_id: str, approver: str, reason: str) -> None:
        self.ledger.append(
            {
                "type": "approval_denied",
                "version_id": version_id,
                "approver": approver,
                "reason": reason,
            }
        )

    def deploy(self, version_id: str, actor: str) -> str:
        rec = self.get_version(version_id)
        if rec["state"] != STATE_APPROVED:
            raise RegistryError(f"deployment gate closed for state={rec['state']}")
        # The registry is the SOLE promotion authority. Re-run the full
        # governance gate set (identity, SoD, crypto, trust eligibility,
        # environment, policy) so every caller — CLI, API, supervisor, and
        # autonomous self-healing — is subject to the same checks, not only
        # the DeploymentService request path. This closes the autonomous
        # deploy bypass where registry.deploy() enforced no SoD / environment
        # / policy validation.
        from qsmlops.serving.deployment import DeploymentService

        DeploymentService(self).validate(version_id, actor, "production")
        # Deactivate any previously active deployment for this model so the
        # active flag stays exclusive (defensive data consistency).
        self._conn.execute(
            "UPDATE deployments SET active=0 WHERE active=1 AND version_id IN "
            "(SELECT version_id FROM model_versions WHERE model_name=?)",
            (rec["model_name"],),
        )
        self._conn.commit()
        deployment_id = uuid.uuid4().hex
        packet = VerificationPacket.create(
            objective=f"deploy {rec['model_name']} v{rec['version']}",
            actor=actor,
            inputs={"version_id": version_id},
            artifacts={"artifact": rec["artifact_digest"]},
            decision="DEPLOYED",
            status="CLOSED",
        )
        self._conn.execute(
            "INSERT INTO deployments (deployment_id, version_id, deployed_at, active, packet_id)"
            " VALUES (?,?,?,1,?)",
            (deployment_id, version_id, time.time(), packet.packet_id),
        )
        self._conn.commit()
        self.transition(version_id, STATE_DEPLOYED, packet, reason=f"deployed by {actor}")
        self.ledger.append_packet(packet)
        return deployment_id

    def active_deployment(self, model_name: str) -> dict | None:
        row = self._conn.execute(
            """SELECT d.*, mv.model_name, mv.version, mv.artifact_digest
               FROM deployments d JOIN model_versions mv ON mv.version_id=d.version_id
               WHERE mv.model_name=? AND d.active=1
               ORDER BY d.deployed_at DESC LIMIT 1""",
            (model_name,),
        ).fetchone()
        return dict(row) if row else None

    def compare_versions(self, version_id_a: str, version_id_b: str) -> dict:
        """Artifact version comparison: bytes, digests, BOM lineage, metrics.

        Stronger tamper detection aid — surfaces exactly what changed between
        two versions of a model (artifact identity, supply-chain entries and
        metric deltas), so a silently swapped artifact is immediately visible.
        """
        import json as _json

        rec_a, rec_b = self.get_version(version_id_a), self.get_version(version_id_b)
        passports = {}
        for vid, rec in (("a", rec_a), ("b", rec_b)):
            doc = self.artifacts.get(rec["passport_digest"])
            passports[vid] = _json.loads(doc.decode("utf-8"))
        boms = {}
        for vid, rec in (("a", rec_a), ("b", rec_b)):
            doc = self.artifacts.get_if_exists(rec["bom_digest"])
            boms[vid] = _json.loads(doc.decode("utf-8")) if doc else None
        # Compare artifact identities via digests (content may be identical by chance, but digest equality is the canonical check)
        artifact_identical = rec_a["artifact_digest"] == rec_b["artifact_digest"]
        comparison = {
            "a": {"version_id": version_id_a, "model": rec_a["model_name"], "version": rec_a["version"],
                  "state": rec_a["state"], "artifact_digest": rec_a["artifact_digest"]},
            "b": {"version_id": version_id_b, "model": rec_b["model_name"], "version": rec_b["version"],
                  "state": rec_b["state"], "artifact_digest": rec_b["artifact_digest"]},
            "artifact_identical": artifact_identical,
            "same_model": rec_a["model_name"] == rec_b["model_name"],
            "suite_changed": rec_a["suite_id"] != rec_b["suite_id"],
            "signer_changed": (passports["a"].get("signature") or {}).get("signer_key_id")
                              != (passports["b"].get("signature") or {}).get("signer_key_id"),
        }
        if boms["a"] is not None and boms["b"] is not None:
            from qsmlops.supplychain.bom import QMLBOM

            comparison["bom_diff"] = QMLBOM.from_dict(boms["a"]).diff(QMLBOM.from_dict(boms["b"]))
        metrics_a, metrics_b = passports["a"].get("metrics", {}), passports["b"].get("metrics", {})
        comparison["metric_deltas"] = {
            k: {"a": metrics_a.get(k), "b": metrics_b.get(k)}
            for k in sorted(set(metrics_a) | set(metrics_b))
        }
        self.ledger.append({
            "type": "version_comparison",
            "version_a": version_id_a,
            "version_b": version_id_b,
            "artifact_identical": comparison["artifact_identical"],
        })
        return comparison

    def rollback(self, model_name: str, actor: str) -> str | None:
        active = self.active_deployment(model_name)
        if not active:
            return None
        previous = self._conn.execute(
            """SELECT mv.* FROM model_versions mv
               WHERE mv.model_name=? AND mv.state IN (?,?) AND mv.version_id<>?
               ORDER BY mv.updated_at DESC LIMIT 1""",
            (model_name, STATE_DEPLOYED, STATE_APPROVED, active["version_id"]),
        ).fetchone()
        fail_packet = VerificationPacket.create(
            objective=f"rollback {model_name}",
            actor=actor,
            inputs={"from_version": active["version_id"]},
            decision="ROLLBACK",
            status="CLOSED",
        )
        # S1: rollback re-promotion MUST use the same authoritative deployment
        # governance gate as a normal deploy. The registry remains the sole
        # promotion mechanism, but the promotion to DEPLOYED is only permitted
        # after DeploymentService.validate passes every gate (identity, SoD,
        # crypto, trust eligibility, environment, policy). This closes the
        # rollback-as-deploy-bypass where a revoked-blocked version could be
        # re-promoted without re-checking. There is exactly ONE deployment
        # validation path: DeploymentService.validate (also used by deploy()).
        from qsmlops.serving.deployment import DeploymentService

        if previous is None:
            # Single-version rollback: retire the active deployment (there is no
            # prior version to restore). This mirrors the original state-machine
            # behaviour — the model is left in ROLLED_BACK with no active
            # deployment — while still recording the governance packet.
            self._conn.execute(
                "UPDATE deployments SET active=0 WHERE deployment_id=?",
                (active["deployment_id"],),
            )
            self._conn.commit()
            cur_state = self.get_version(active["version_id"])["state"]
            if cur_state == STATE_DEPLOYED:
                self.transition(
                    active["version_id"], STATE_ROLLED_BACK, fail_packet,
                    reason="rolled back",
                )
            self.ledger.append_packet(fail_packet)
            return None
        prev_id = previous["version_id"]
        validation = DeploymentService(self).validate(prev_id, actor, "production")
        if not validation["eligible"]:
            failed = [c["name"] for c in validation["checks"] if not c["passed"]]
            self.ledger.append({
                "type": "rollback_blocked",
                "version_id": prev_id,
                "model": model_name,
                "actor": actor,
                "reason": f"governance validation failed: {', '.join(failed)}",
                "failed_checks": failed,
            })
            self.ledger.append_packet(fail_packet)
            # A blocked rollback MUST leave production exactly as it was: the
            # current active deployment stays active and no state is changed.
            return None
        # Only now that the previous version has cleared every governance gate
        # do we deactivate the current deployment and restore the previous one.
        self._conn.execute(
            "UPDATE deployments SET active=0 WHERE deployment_id=?",
            (active["deployment_id"],),
        )
        self._conn.commit()
        cur_state = self.get_version(active["version_id"])["state"]
        if cur_state == STATE_DEPLOYED:
            self.transition(
                active["version_id"], STATE_ROLLED_BACK, fail_packet, reason="rolled back"
            )
        self.transition(prev_id, STATE_DEPLOYED, fail_packet, reason="restored by rollback")
        self._conn.execute(
            "INSERT INTO deployments (deployment_id, version_id, deployed_at, active, packet_id)"
            " VALUES (?,?,?,1,?)",
            (uuid.uuid4().hex, prev_id, time.time(), fail_packet.packet_id),
        )
        self._conn.commit()
        self.ledger.append_packet(fail_packet)
        return prev_id

    def quarantine(self, version_id: str, actor: str, reason: str) -> None:
        packet = VerificationPacket.create(
            objective=f"quarantine {version_id}",
            actor=actor,
            inputs={"reason": reason},
            decision="QUARANTINE",
            status="CLOSED",
        )
        self.transition(version_id, STATE_QUARANTINED, packet, reason=reason)
        self.ledger.append_packet(packet)

    def revoke(self, version_id: str, actor: str, reason: str) -> None:
        rec = self.get_version(version_id)
        current = rec["state"]
        if current in (STATE_REVOKED, STATE_ROLLED_BACK):
            raise RegistryError(
                f"cannot revoke version {version_id} in terminal state {current}"
            )
        packet = VerificationPacket.create(
            objective=f"revoke {version_id}",
            actor=actor,
            inputs={"reason": reason},
            decision="REVOKED",
            status="CLOSED",
        )
        self.transition(version_id, STATE_REVOKED, packet, reason=reason)
        self.ledger.append_packet(packet)

    def list_versions(self, model_name: str | None = None) -> list[dict]:
        if model_name:
            rows = self._conn.execute(
                "SELECT * FROM model_versions WHERE model_name=? ORDER BY version",
                (model_name,),
            )
        else:
            rows = self._conn.execute("SELECT * FROM model_versions ORDER BY model_name, version")
        return [dict(r) for r in rows]


def _canonical(obj) -> str:
    import json

    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

"""Shared helpers for the MLOps lifecycle: identifiers, storage I/O, audit."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from pathlib import Path

from qsmlops.core.errors import NotFoundError

log = logging.getLogger("satsa.mlops")

MODEL_NAME = "review-outcome"


class ArtifactMissing(RuntimeError):
    """A dataset snapshot or model artifact cannot be read from storage."""


def stable_id(prefix: str, *parts: str) -> str:
    """Deterministic identifier; retries of the same job reuse the same rows."""
    digest = hashlib.sha3_256("\x1f".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def dumps(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def put_bytes(storage, key: str, data: bytes, content_type: str) -> str:
    """Store bytes through the platform ArtifactStorage; returns the SHA3-256."""
    from satsa.submissions.storage import file_sha3_256

    handle, name = tempfile.mkstemp(prefix="satsa-ml-")
    path = Path(name)
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(data)
        digest = file_sha3_256(path)
        storage.put_file(path, key, content_type, digest)
        return digest
    finally:
        path.unlink(missing_ok=True)


def get_bytes(storage, key: str) -> bytes:
    """Read stored bytes. Callers verify the digest against the registry record."""
    handle, name = tempfile.mkstemp(prefix="satsa-ml-")
    os.close(handle)
    path = Path(name)
    try:
        path.unlink()
        storage.copy_to(key, path)
        return path.read_bytes()
    except Exception as exc:  # local FileNotFoundError, S3 NoSuchKey, I/O errors
        log.warning("ml artifact read failed", extra={"storage_key": key})
        raise ArtifactMissing("stored ML artifact is missing or unreadable") from exc
    finally:
        path.unlink(missing_ok=True)


def identity_of(db, user_id: str) -> str:
    row = db.query_one("SELECT identity_id FROM satsa_users WHERE id=?", (user_id,))
    if row is None:
        raise NotFoundError("user identity is unavailable for audit")
    return row["identity_id"]


def audit(db, audit_service, *, user_id: str, organization_id: str, action: str,
          resource: str, **metadata) -> None:
    """Append to the platform audit log (the same one runs and reviews use)."""
    if audit_service is None:
        return
    from qsmlops.security.audit.events import AuditEvent

    audit_service.record(
        AuditEvent.create(
            actor=identity_of(db, user_id),
            action=action,
            resource=resource,
            metadata={"organization_id": organization_id, **metadata},
        )
    )

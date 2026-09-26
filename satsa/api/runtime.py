"""Shared API/worker runtime configuration and storage wiring."""

import os
from pathlib import Path

from qsmlops.database.engine import create_engine
from qsmlops.database.migrations import MigrationRunner
from qsmlops.evidence.ledger import EvidenceLedger
from qsmlops.security.audit.service import AuditService
from qsmlops.security.identity.service import IdentityService
from satsa.submissions.storage import LocalArtifactStorage, S3ArtifactStorage


def build_runtime():
    database_url = os.getenv("SATSA_DATABASE_URL") or os.getenv("QSMLOPS_DB_URL")
    if not database_url:
        database_path = Path(os.getenv("SATSA_DB", "satsa_api.db")).resolve()
        database_url = f"sqlite:///{database_path.as_posix()}"
    engine = create_engine(database_url)
    MigrationRunner(engine).migrate()
    data_dir = Path(os.getenv("SATSA_DATA_DIR", ".satsa-api")).resolve()
    ledger_path = Path(
        os.getenv("SATSA_LEDGER_PATH", str(data_dir / "evidence-ledger.jsonl"))
    ).resolve()
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    audit = AuditService(EvidenceLedger(ledger_path), database=engine)
    identity = IdentityService(
        engine,
        AuditService(
            EvidenceLedger(ledger_path.parent / "identity-audit-ledger.jsonl"),
            database=engine,
        ),
    )
    key_dir = Path(os.getenv("SATSA_TRUST_KEY_DIR", str(data_dir / "keys"))).resolve()
    key_dir.mkdir(parents=True, exist_ok=True)
    bucket = os.getenv("SATSA_S3_BUCKET", "")
    if bucket:
        import boto3
        from botocore.config import Config

        config = (
            Config(s3={"addressing_style": "path"})
            if os.getenv("SATSA_S3_PATH_STYLE", "true").lower() == "true"
            else None
        )
        client = boto3.client(
            "s3",
            endpoint_url=os.getenv("SATSA_S3_ENDPOINT_URL") or None,
            region_name=os.getenv("SATSA_S3_REGION", "us-east-1"),
            config=config,
        )
        storage = S3ArtifactStorage(
            bucket=bucket, prefix=os.getenv("SATSA_S3_PREFIX", ""), client=client
        )
    else:
        root = Path(
            os.getenv("SATSA_ARTIFACTS_DIR", str(data_dir / "artifacts"))
        ).resolve()
        storage = LocalArtifactStorage(root)
    return engine, audit, identity, storage, key_dir

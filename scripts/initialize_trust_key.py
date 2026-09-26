"""Provision a local TRUST-SAT key into a mounted key directory."""

from __future__ import annotations

import os
from pathlib import Path

from qsmlops.database.engine import create_engine
from satsa.analysis.trust import TrustService


def main() -> int:
    key_dir = Path(os.environ["SATSA_TRUST_KEY_DIR"])
    database_url = os.environ["SATSA_DATABASE_URL"]
    engine = create_engine(database_url)
    try:
        TrustService(engine, key_dir, organization_id="deployment-bootstrap")
        print("TRUST-SAT signing key is present")
        return 0
    finally:
        engine.close()


if __name__ == "__main__":
    raise SystemExit(main())

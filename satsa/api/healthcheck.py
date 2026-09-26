"""Container readiness checks for API and worker services."""

from __future__ import annotations

import argparse

from qsmlops.database.migrations import MigrationRunner
from satsa.api.runtime import build_runtime


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=("api", "worker"), required=True)
    role = parser.parse_args().role
    engine, _audit, _identity, storage, _key_dir = build_runtime(migrate=False)
    try:
        engine.query_one("SELECT 1 AS ready")
        if not MigrationRunner(engine).status()["is_current"]:
            return 1
        storage.check_ready()
        if role == "worker":
            engine.query_one("SELECT COUNT(*) AS jobs FROM satsa_execution_jobs")
        print(f"{role} ready")
        return 0
    except Exception:  # noqa: BLE001 - readiness must report dependency failures uniformly.
        return 1
    finally:
        storage.close()
        engine.close()


if __name__ == "__main__":
    raise SystemExit(main())

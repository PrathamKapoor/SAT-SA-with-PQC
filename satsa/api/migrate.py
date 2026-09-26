"""Explicit database migration commands for deployment jobs."""

from __future__ import annotations

import argparse

from qsmlops.database.engine import create_engine
from qsmlops.database.migrations import MigrationRunner
from satsa.api.runtime import RuntimeSettings


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m satsa.api.migrate")
    parser.add_argument("command", choices=("status", "check", "upgrade"))
    args = parser.parse_args()
    settings = RuntimeSettings.from_env()
    engine = create_engine(
        settings.database_url,
        pool_min_size=settings.db_pool_min_size,
        pool_max_size=settings.db_pool_max_size,
        connect_timeout=settings.db_connect_timeout,
        pool_timeout=settings.db_pool_timeout,
        statement_timeout_ms=settings.db_statement_timeout_ms,
    )
    try:
        runner = MigrationRunner(engine)
        if args.command == "upgrade":
            applied = runner.migrate()
            print("applied: " + (", ".join(applied) if applied else "none"))
        status = runner.status()
        print(
            f"schema current={status['current_version']} "
            f"target={status['target_version']} ready={status['is_current']}"
        )
        if args.command == "check" and not status["is_current"]:
            return 1
        return 0
    finally:
        engine.close()


if __name__ == "__main__":
    raise SystemExit(main())

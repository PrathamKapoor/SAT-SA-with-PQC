"""Launch the SAT-SA web UI locally.

There was no standalone launcher before this — the UI was only ever
exercised through FastAPI's TestClient in tests. This boots a real
uvicorn server against a persistent SQLite DB and, if that DB is
empty, loads the committed demo dataset so there's something to
look at immediately.

Usage:
    python scripts/serve_ui.py [--db PATH] [--trust-key-dir PATH]
                                [--host HOST] [--port PORT] [--no-demo]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="satsa_ui.db")
    ap.add_argument("--trust-key-dir", default="satsa_ui_keys")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-demo", action="store_true",
                     help="skip loading the demo dataset even if the DB is empty")
    args = ap.parse_args()

    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    from satsa.service import SatsaService
    from satsa.ui import create_app

    db_path = Path(args.db)
    trust_key_dir = Path(args.trust_key_dir)
    trust_key_dir.mkdir(parents=True, exist_ok=True)

    eng = SQLiteDatabaseEngine(db_path)
    eng.connect()
    MigrationRunner(eng).migrate()
    svc = SatsaService(eng)

    existing = eng.query_one("SELECT COUNT(*) AS n FROM satsa_entities")
    if not args.no_demo and (existing is None or existing["n"] == 0):
        from satsa.ui.demo import load_demo_assessment
        print(f"[serve_ui] {db_path} is empty — loading the committed demo dataset")
        load_demo_assessment(svc, trust_key_dir)

    app = create_app(svc, trust_key_dir=trust_key_dir)

    import uvicorn
    print(f"[serve_ui] serving SAT-SA UI at http://{args.host}:{args.port} "
          f"(db={db_path}, trust_key_dir={trust_key_dir})")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Phase 18 — offline hardening: prove that running the SAT-SA
ingestion + analytics + UI pipeline does not require network
access.

The test imports every public SAT-SA surface and runs a small
end-to-end scenario, while a socket monkey-patch blocks any
attempt to open a real network connection. If anything tries
to reach out, the patch raises immediately.
"""
from __future__ import annotations

import socket
import tempfile
from pathlib import Path
from unittest import mock


def test_full_pipeline_does_not_open_network():
    """Run the demo loader end-to-end with all socket calls blocked."""
    blocked: list[tuple] = []

    def _blocked(*args, **kwargs):
        blocked.append((args, kwargs))
        raise RuntimeError("network blocked")

    td = tempfile.mkdtemp(prefix="offline_")
    try:
        from qsmlops.database.engine import SQLiteDatabaseEngine
        from qsmlops.database.migrations import MigrationRunner
        engine = SQLiteDatabaseEngine(Path(td) / "offline.db")
        engine.connect()
        MigrationRunner(engine).migrate()

        from satsa.service import SatsaService
        svc = SatsaService(engine)

        # Block only the *outbound* network primitives. Do NOT patch
        # socket.socket or httpx.Client — those are used by the
        # TestClient and asyncio's event loop. We block the network
        # entry points: gethostbyname (DNS) and create_connection
        # (TCP).
        with mock.patch.object(socket, "create_connection", side_effect=_blocked), \
             mock.patch.object(socket, "gethostbyname", side_effect=_blocked), \
             mock.patch("urllib.request.urlopen", side_effect=_blocked):
            # 1. ingest + run for one CSE
            e = svc.register_entity("CSE-OFFLINE", sector="defence")
            a = svc.open_assessment(e.id, 1735689600.0, 1738281600.0)
            from scripts.build_demo_dataset import healthy_cse
            src = Path(td) / "sub"
            healthy_cse(src)
            svc.submit(a.id, src)
            svc.run_analysis(e.id, a.id,
                              trust_key_dir=Path(td) / "keys")
            svc.compute_risk(e.id)
            svc.prioritize_entities()
            svc.prioritize_findings(svc._db.query_one(
                "SELECT id FROM satsa_runs ORDER BY created_at DESC LIMIT 1")["id"])

            # 2. build the UI
            from satsa.ui import create_app
            app = create_app(svc, trust_key_dir=Path(td) / "keys")
            from fastapi.testclient import TestClient
            client = TestClient(app)
            client.post("/demo/load")
            for path in ("/", "/entities", "/findings", "/queue",
                          "/benchmarks", "/evidence", "/system"):
                r = client.get(path)
                assert r.status_code == 200
    finally:
        try:
            engine.close()
        except Exception:
            pass
        import shutil
        shutil.rmtree(td, ignore_errors=True)

    assert blocked == [], (
        f"the pipeline tried to open {len(blocked)} socket(s): {blocked[:3]}")


def test_no_runtime_internet_dependency_in_satsa():
    """No import-time or module-level reference to remote URLs or
    CDNs anywhere in satsa/."""
    import re
    from pathlib import Path
    base = Path(__file__).resolve().parent.parent / "satsa"
    pattern = re.compile(
        rb"https?://(?!127\.0\.0\.1|localhost|0\.0\.0\.0)[^\s\"'<>)]+"
    )
    offenders: list[str] = []
    for p in base.rglob("*.py"):
        try:
            data = p.read_bytes()
        except OSError:
            continue
        for m in pattern.finditer(data):
            offenders.append(f"{p.relative_to(base.parent)}: {m.group(0)!r}")
    # comments mentioning local / official CDNs are fine; the only
    # allowed remote URL string would be in a future real config
    assert not offenders, (
        f"unexpected remote URL references in satsa/: {offenders[:5]}")

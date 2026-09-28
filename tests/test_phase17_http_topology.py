"""Real HTTP workflow: API process + separate worker process + database.

Starts `python -m satsa.api.server` and the worker entry point as real
subprocesses, bootstraps an organization administrator, and runs the portable
`scripts/deployment_smoke.py` against them over HTTP. Nothing is mocked. The
PostgreSQL variant needs SATSA_TEST_POSTGRES_DSN (an isolated schema per run).
"""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

pytest_plugins = ["test_postgres_engine"]

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(params=["sqlite", "postgresql"])
def database_url(request, tmp_path):
    if request.param == "sqlite":
        return f"sqlite:///{(tmp_path / 'satsa.db').as_posix()}"
    return request.getfixturevalue("postgres_dsn")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _run(args, env, **kwargs):
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
        **kwargs,
    )


def _wait_ready(base: str, api: subprocess.Popen, seconds: float = 60) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if api.poll() is not None:
            raise AssertionError("API process exited before becoming ready")
        try:
            with urllib.request.urlopen(f"{base}/health/ready", timeout=2) as r:
                if r.status == 200:
                    return
        except OSError:
            pass
        time.sleep(0.5)
    raise AssertionError("API never became ready")


def test_api_and_worker_processes_complete_the_workflow(database_url, tmp_path):
    with (
        (tmp_path / "api.log").open("w") as api_log,
        (tmp_path / "worker.log").open("w") as worker_log,
    ):
        _workflow(database_url, tmp_path, {"api": api_log, "worker": worker_log})


def _workflow(database_url, tmp_path, logs) -> None:
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT),
        "SATSA_ENVIRONMENT": "development",
        "SATSA_DATABASE_URL": database_url,
        "SATSA_DATA_DIR": str(tmp_path / "data"),
        "SATSA_TRUST_KEY_DIR": str(tmp_path / "keys"),
        "SATSA_LEDGER_PATH": str(tmp_path / "ledger.jsonl"),
        "SATSA_STORAGE_BACKEND": "local",
        "SATSA_AUTO_MIGRATE": "false",
        "SATSA_API_PORT": str(port),
        "SATSA_COOKIE_SECURE": "false",
    }
    migrate = _run(["-m", "satsa.api.migrate", "upgrade"], env)
    assert migrate.returncode == 0, migrate.stderr
    key = _run(["scripts/initialize_trust_key.py"], env)
    assert key.returncode == 0, key.stderr

    api = subprocess.Popen(
        [sys.executable, "-m", "satsa.api.server"],
        cwd=ROOT,
        env=env,
        stdout=logs["api"],
        stderr=subprocess.STDOUT,
    )
    worker = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "from satsa.analysis.execution import worker_main; worker_main()",
        ],
        cwd=ROOT,
        env=env,
        stdout=logs["worker"],
        stderr=subprocess.STDOUT,
    )
    try:
        _wait_ready(base, api)
        bootstrap = _run(
            [
                "scripts/bootstrap_satsa_admin.py",
                "--database-url",
                database_url,
                "--ledger",
                str(tmp_path / "identity-ledger.jsonl"),
                "--name",
                "Topology test admin",
                "--email",
                "topology-admin@example.test",
                "--organization",
                "Topology test organization",
            ],
            env,
        )
        assert bootstrap.returncode == 0, bootstrap.stderr
        lines = bootstrap.stdout.strip().splitlines()
        organization = next(
            line.split("=", 1)[1]
            for line in lines
            if line.startswith("organization_id=")
        )
        report_path = tmp_path / "smoke-report.json"
        smoke = _run(
            [
                "scripts/deployment_smoke.py",
                "--provision",
                "--report",
                str(report_path),
            ],
            {
                **env,
                "SATSA_SMOKE_API_URL": base,
                "SATSA_SMOKE_ORGANIZATION_ID": organization,
                "SATSA_SMOKE_ADMIN_CREDENTIAL": lines[-1],
                "SATSA_SMOKE_TIMEOUT_SECONDS": "240",
            },
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        statuses = {check["check"]: check["status"] for check in report["checks"]}
        assert smoke.returncode == 0, (statuses, smoke.stderr[-2000:])
        assert report["status"] == "passed"
        assert set(statuses.values()) == {"PASS"}
        assert {
            "tenant_isolation",
            "evidence_records",
            "priorities",
            "decision",
            "trust_finalization",
            "verification",
            "audit",
        } <= set(statuses)
        assert report["finding_count"] >= 1
    finally:
        for process in (worker, api):
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()

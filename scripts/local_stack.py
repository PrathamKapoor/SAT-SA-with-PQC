"""Run the SAT-SA backend locally for the web workbench: offline, SQLite.

Starts the API server and a separate analysis worker against a SQLite
database and local artifact storage under --data-dir, with no network
dependency. On first start it applies migrations, creates the TRUST-SAT
signing key, bootstraps an organization administrator and adds an analyst
and a supervisor through the API, then writes their credentials to
<data-dir>/credentials.json (local development only; the file is created
with owner-only permissions where the platform supports it).

    python scripts/local_stack.py                 # API on http://127.0.0.1:8000
    python scripts/local_stack.py --seed-demo     # also load the five-CSE demo through the API

Then, in web/:  SATSA_API_BASE_URL=http://127.0.0.1:8000 npm run dev
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _env(data: Path, port: int) -> dict[str, str]:
    return {
        **os.environ,
        "PYTHONPATH": str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", ""),
        "SATSA_ENVIRONMENT": "development",
        "SATSA_DATABASE_URL": f"sqlite:///{(data / 'satsa.db').as_posix()}",
        "SATSA_DATA_DIR": str(data),
        "SATSA_TRUST_KEY_DIR": str(data / "keys"),
        "SATSA_LEDGER_PATH": str(data / "ledger.jsonl"),
        "SATSA_STORAGE_BACKEND": "local",
        "SATSA_AUTO_MIGRATE": "false",
        "SATSA_API_PORT": str(port),
        "SATSA_COOKIE_SECURE": "false",
    }


def _run(args: list[str], env: dict[str, str]) -> str:
    result = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise SystemExit(f"{' '.join(args)} failed:\n{result.stderr}")
    return result.stdout


def _post(base: str, path: str, token: str, organization: str, body: dict) -> dict:
    request = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Organization-ID": organization,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def _wait_ready(base: str, api: subprocess.Popen, seconds: float = 60) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if api.poll() is not None:
            raise SystemExit("the API process exited; see its log")
        try:
            with urllib.request.urlopen(f"{base}/health/ready", timeout=2):
                return
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    raise SystemExit("the API did not become ready")


def _write_private(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def start(
    data: Path, port: int, *, seed_demo: bool, log_dir: Path | None = None
) -> tuple[subprocess.Popen, subprocess.Popen, dict]:
    data.mkdir(parents=True, exist_ok=True)
    env = _env(data, port)
    base = f"http://127.0.0.1:{port}"
    _run(["-m", "satsa.api.migrate", "upgrade"], env)
    _run(["scripts/initialize_trust_key.py"], env)
    logs = log_dir or data
    api = subprocess.Popen(
        [sys.executable, "-m", "satsa.api.server"],
        cwd=ROOT,
        env=env,
        stdout=open(logs / "api.log", "a"),  # noqa: SIM115 (lives as long as the process)
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
        stdout=open(logs / "worker.log", "a"),  # noqa: SIM115 (lives as long as the process)
        stderr=subprocess.STDOUT,
    )
    _wait_ready(base, api)
    credentials_file = data / "credentials.json"
    if credentials_file.exists():
        credentials = json.loads(credentials_file.read_text(encoding="utf-8"))
    else:
        out = _run(
            [
                "scripts/bootstrap_satsa_admin.py",
                "--database-url",
                env["SATSA_DATABASE_URL"],
                "--ledger",
                str(data / "identity-ledger.jsonl"),
                "--name",
                "Local administrator",
                "--email",
                "admin@local.test",
                "--organization",
                "Local organization",
            ],
            env,
        )
        lines = out.strip().splitlines()
        organization = next(
            line.split("=", 1)[1]
            for line in lines
            if line.startswith("organization_id=")
        )
        admin = lines[-1]
        credentials = {"api": base, "organization_id": organization, "admin": admin}
        for role in ("analyst", "supervisor"):
            invited = _post(
                base,
                "/api/v1/members",
                admin,
                organization,
                {
                    "name": f"Local {role}",
                    "email": f"{role}@local.test",
                    "role": f"satsa_{role}",
                },
            )
            credentials[role] = invited["credential"]
        _write_private(credentials_file, json.dumps(credentials, indent=2))
    if seed_demo:
        _run(
            [
                "scripts/seed_demo_via_api.py",
                "--api",
                base,
                "--credential",
                credentials["admin"],
                "--organization",
                credentials["organization_id"],
                "--wait",
            ],
            env,
        )
    return api, worker, credentials


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=ROOT / ".satsa-local")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--seed-demo", action="store_true")
    args = parser.parse_args(argv)
    api, worker, credentials = start(
        args.data_dir.resolve(), args.port, seed_demo=args.seed_demo
    )
    print(f"SAT-SA API: {credentials['api']}  (logs in {args.data_dir})", flush=True)
    print(f"Organization: {credentials['organization_id']}")
    print(
        f"Credentials for sign-in (local development only): {args.data_dir / 'credentials.json'}"
    )
    print(
        "Web UI:  cd web && SATSA_API_BASE_URL=" + credentials["api"] + " npm run dev"
    )
    try:
        while api.poll() is None and worker.poll() is None:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for process in (worker, api):
            process.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

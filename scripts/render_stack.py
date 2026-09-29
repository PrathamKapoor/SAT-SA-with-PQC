"""Run the hosted Render presentation stack in one container.

Render's free web services have no private network and no persistent disk,
so the SAT-SA API, the analysis worker and the Next.js workbench run
together here: the API listens on 127.0.0.1 only and the web server is the
single public process on $PORT. State lives under --data-dir and is rebuilt
on every container start (demo data only, SQLite and local artifact storage).

Sign-in credentials would otherwise change on every restart. When
SATSA_LOGIN_SEED is set, each role's credential is derived from it, so the
same credentials keep working across restarts and redeploys; they are
written to the service log at start-up. Unset, the random credentials from
the bootstrap are logged instead.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import os
import subprocess
import threading
import time
from pathlib import Path

from local_stack import _env, _run, start

from qsmlops.database.engine import create_engine
from qsmlops.database.repositories import IdentityCredentialRepository
from qsmlops.security.identity.auth import _hash_secret, split_token

ROLES = ("admin", "analyst", "supervisor")


def _derived(seed: str, role: str) -> tuple[str, str]:
    """A stable (key_id, secret) pair for one role, derived from the seed."""
    digest = hmac.new(seed.encode(), role.encode(), hashlib.sha256).hexdigest()
    return digest[:16], digest[16:]


def _pin_credentials(database_url: str, credentials: dict, seed: str) -> dict:
    """Replace each role's bootstrap credential with its seed-derived one."""
    db = create_engine(database_url)
    try:
        repo = IdentityCredentialRepository(db)
        pinned = {}
        for role in ROLES:
            key_id, _ = split_token(credentials[role])
            row = repo.get_by_key_id(key_id)
            new_key_id, secret = _derived(seed, role)
            salt = os.urandom(16).hex()
            with db.transaction():
                repo.set_credential(
                    row["identity_id"],
                    new_key_id,
                    _hash_secret(secret, salt),
                    salt,
                    created_at=time.time(),
                )
            pinned[role] = f"{new_key_id}.{secret}"
        return pinned
    finally:
        db.close()


def _seed_demo(base: str, credentials: dict, env: dict[str, str]) -> None:
    try:
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
        print("Demo data loaded.", flush=True)
    except SystemExit as exc:
        print(f"Demo data could not be loaded: {exc}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=Path("/data/satsa"))
    parser.add_argument("--web-dir", type=Path, default=Path("/web"))
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--no-demo", action="store_true")
    args = parser.parse_args(argv)
    data = args.data_dir.resolve()

    api, worker, credentials = start(data, args.api_port, seed_demo=False)
    base = credentials["api"]
    env = _env(data, args.api_port)
    seed = os.environ.get("SATSA_LOGIN_SEED", "").strip()
    logins = (
        _pin_credentials(env["SATSA_DATABASE_URL"], credentials, seed)
        if seed
        else {role: credentials[role] for role in ROLES}
    )
    credentials.update(logins)
    print("SAT-SA sign-in credentials:", flush=True)
    for role in ROLES:
        print(f"  {role:<10} {logins[role]}", flush=True)

    web = subprocess.Popen(
        ["node", "server.js"],
        cwd=args.web_dir,
        env={
            **os.environ,
            "SATSA_API_BASE_URL": base,
            "HOSTNAME": "0.0.0.0",
            "PORT": os.environ.get("PORT", "10000"),
        },
    )
    if not args.no_demo:
        threading.Thread(target=_seed_demo, args=(base, credentials, env), daemon=True).start()

    processes = (web, api, worker)
    try:
        while all(p.poll() is None for p in processes):
            time.sleep(1)
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
    return next((p.returncode or 1) for p in processes if p.poll() is not None)


if __name__ == "__main__":
    raise SystemExit(main())

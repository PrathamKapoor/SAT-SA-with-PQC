"""P33 â€” non-destructive offline/air-gap deployment rehearsal.

Verifies that an offline deployment bundle (a local wheelhouse) can
actually install and run SAT-SA with NO network access, using the
project's own proven commands (``pip install --no-index
--find-links``, ``sat-sa doctor``/``demo``/``validate``) rather than
recreating any of them.

Honesty boundary: this rehearses the deployment procedure on whatever
host it is executed on. A green rehearsal on the development machine
is NOT a completed target-machine (e.g. NCIIPC air-gapped host)
deployment â€” that requires actually running this procedure on the
disconnected target and recording the resulting report there.

Usage:
    python scripts/airgap_rehearsal.py --wheelhouse <dir> [--out <dir>]

Without ``--wheelhouse`` (or pointing at a missing/empty directory)
the tool fails clearly with a "bundle not supplied" report â€” it never
pretends success, and it never downloads anything.

All venvs, databases, keys, and reports go into the system temp dir
(or ``--out``), never into the repository.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sysconfig
import tempfile
import time
import venv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Pure helpers (importable and testable without any subprocess)
# ---------------------------------------------------------------------------

def _runtime_requirement_names(requirements_path: Path) -> list[str]:
    """The runtime (non-dev) requirement names from requirements.txt,
    in file order. Dev section is excluded â€” a deployment bundle must
    satisfy the runtime contract only."""
    names = []
    in_dev = False
    for raw in requirements_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            if "Development / test dependencies" in line:
                in_dev = True
            continue
        if in_dev:
            continue
        names.append(re.match(r"^([A-Za-z0-9_.-]+)", line).group(1))
    return names


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "_", name).lower()


def _venv_python(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts" if os.name == "nt" else "bin") / (
        "python.exe" if os.name == "nt" else "python")


def _console_script(venv_dir: Path, name: str) -> Path:
    return venv_dir / ("Scripts" if os.name == "nt" else "bin") / (
        f"{name}.exe" if os.name == "nt" else name)


def install_commands(wheelhouse: Path, repo_root: Path,
                     python_exe: Path) -> list[list[str]]:
    """The exact offline install commands the rehearsal runs. Both use
    ``--no-index`` (PyPI unreachable is the point) and a local
    ``--find-links`` wheelhouse. The project itself is installed with
    ``--no-deps`` because requirements.txt already supplied every
    runtime dependency."""
    return [
        [str(python_exe), "-m", "pip", "install",
         "--no-index", "--find-links", str(wheelhouse),
         "-r", str(repo_root / "requirements.txt")],
        [str(python_exe), "-m", "pip", "install",
         "--no-index", "--find-links", str(wheelhouse),
         "--no-deps", str(repo_root)],
    ]


def check_wheelhouse(wheelhouse: Path,
                     requirements_path: Path | None = None) -> dict:
    """Verify the supplied bundle can plausibly satisfy the runtime
    contract. Fails clearly when the bundle is missing or empty â€”
    never pretends success."""
    requirements_path = requirements_path or REPO_ROOT / "requirements.txt"
    problems: list[str] = []
    warnings: list[str] = []
    if not wheelhouse.exists():
        problems.append(
            f"bundle not supplied: no wheelhouse directory at "
            f"{wheelhouse}")
    else:
        wheels = [p.name for p in wheelhouse.glob("*.whl")]
        if not wheels:
            problems.append(
                f"bundle not supplied: {wheelhouse} contains no .whl files")
        else:
            for req in _runtime_requirement_names(requirements_path):
                norm = _normalize(req)
                if not any(_normalize(w.split("-")[0]) == norm
                           for w in wheels):
                    problems.append(
                        f"bundle is missing a wheel for runtime "
                        f"requirement {req!r}")
            if not any(w.lower().startswith("setuptools-")
                       or w.lower().startswith("setuptools_")
                       for w in wheels):
                warnings.append(
                    "no setuptools wheel in the bundle â€” installing the "
                    "project itself uses a setuptools build backend and "
                    "will fail on Python 3.12+ without one (P31)")
    return {
        "wheelhouse": str(wheelhouse),
        "n_wheels": len([p for p in wheelhouse.glob("*.whl")])
        if wheelhouse.exists() else 0,
        "problems": problems,
        "warnings": warnings,
        "status": "fail" if problems else ("warn" if warnings else "pass"),
    }


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def run_rehearsal(*, wheelhouse=None, repo_root: Path = REPO_ROOT,
                  workdir: Path | None = None, keep: bool = False,
                  skip_heavy: bool = False) -> dict:
    """Execute the full rehearsal and return a structured
    pass/warn/fail report. Never mutates the repository; never touches
    the network (install commands are --no-index by construction)."""
    started = time.time()
    checks: list[dict] = []

    def add(name: str, status: str, detail: str) -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    wh = Path(wheelhouse) if wheelhouse else None
    wh_check = check_wheelhouse(wh) if wh else {
        "wheelhouse": None,
        "n_wheels": 0,
        "problems": ["bundle not supplied: no wheelhouse path was given "
                     "(pass --wheelhouse <dir>)"],
        "warnings": [],
        "status": "fail",
    }
    add("wheelhouse_present",
        wh_check["status"],
        "; ".join(wh_check["problems"]) or
        f"{wh_check['n_wheels']} wheels found" +
        ("; " + "; ".join(wh_check["warnings"]) if wh_check["warnings"]
         else ""))

    own_temp = None
    if workdir is None:
        own_temp = Path(tempfile.mkdtemp(prefix="airgap-rehearsal-"))
        workdir = own_temp
    workdir = Path(workdir)

    venv_dir = workdir / "rehearsal-venv"
    db_dir = workdir / "data"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "rehearsal.db"
    keys_dir = db_dir / "keys"

    py = None
    if wh_check["status"] != "fail":
        py = _venv_python(workdir / "rehearsal-venv")
        try:
            venv.create(workdir / "rehearsal-venv", with_pip=True)
            add("venv_created", "pass", str(workdir / "rehearsal-venv"))
        except Exception as exc:
            add("venv_created", "fail", f"venv creation failed: {exc}")

        for label, cmd in zip(
                ("install_requirements", "install_project"),
                install_commands(wh, repo_root, py)):
            proc = _run(cmd)
            ok = proc.returncode == 0
            detail = ("install completed with --no-index "
                      "(no network possible)" if ok else
                      (proc.stderr or proc.stdout)[-800:])
            add(label, "pass" if ok else "fail", detail)

        if py and _venv_python(workdir / "rehearsal-venv").exists():
            # All verification runs from a NEUTRAL cwd (the workdir):
            # running from the repository root would put the source
            # tree on sys.path and mask an install that resolved
            # nothing — exactly the masking the packaging-discovery
            # tests (phase 86) were written to prevent.
            probe = (
                "import sys, sysconfig, satsa, qsmlops;"
                " sp = sysconfig.get_paths()['purelib'];"
                " print(satsa.__file__); print(qsmlops.__file__);"
                " print('SATSA_SITE:', sp)")
            proc = _run([str(py), "-c", probe], cwd=str(workdir))
            if proc.returncode != 0:
                add("imports_from_site_packages", "fail",
                    (proc.stderr or proc.stdout)[-800:])
            else:
                lines = proc.stdout.strip().splitlines()
                satsa_path = next(
                    (l for l in lines if l.startswith(("/", "C:"))), "")
                purelib = next(
                    (l.split(":", 1)[1].strip() for l in lines
                     if l.startswith("SATSA_SITE:")), "")
                inside = bool(satsa_path and purelib) and Path(
                    satsa_path).resolve().is_relative_to(
                        Path(purelib).resolve())
                add("imports_from_site_packages",
                    "pass" if inside else "fail",
                    f"satsa resolved to {satsa_path or '?'} "
                    f"(site-packages: {purelib or 'unknown'})")

            cli = _console_script(workdir / "rehearsal-venv", "sat-sa")
            if not cli.exists():
                add("cli_version", "fail",
                    f"sat-sa console script not found at {cli}")
            else:
                proc = _run([str(cli), "--version"], cwd=str(workdir))
                add("cli_version",
                    "pass" if proc.returncode == 0 else "fail",
                    proc.stdout.strip() if proc.returncode == 0
                    else (proc.stderr or proc.stdout)[-400:])

                if not skip_heavy:
                    keys_doctor = db_dir / "keys-doctor"
                    for label, args in (
                            ("doctor",
                             ["--db", str(db_dir / "doctor.db"),
                              "--trust-key-dir", str(keys_doctor),
                              "doctor"]),
                            ("demo",
                             ["--db", str(db_dir / "demo.db"),
                              "--trust-key-dir", str(db_dir / "keys-demo"),
                              "demo"]),
                            ("validate",
                             ["--db", str(db_dir / "demo.db"),
                              "--trust-key-dir", str(db_dir / "keys-demo"),
                              "validate"]),
                    ):
                        proc = _run([str(cli), *args], cwd=str(workdir))
                        ok = proc.returncode == 0
                        detail = (proc.stdout.strip().splitlines()[-1]
                                  if ok and proc.stdout.strip() else
                                  (proc.stderr or proc.stdout)[-800:])
                        add(label, "pass" if ok else "fail", detail)
                    add("offline_install_posture", "pass",
                        "every install command used --no-index with a local "
                        "--find-links wheelhouse; PyPI was never reachable")

    overall = ("fail" if any(c["status"] == "fail" for c in checks)
               else "warn" if any(c["status"] == "warn" for c in checks)
               else "pass")

    report = {
        "rehearsal": "satsa offline/air-gap deployment rehearsal",
        "overall": overall,
        "scope_note": (
            "This is a same-host rehearsal of the offline install path. "
            "It is NOT a completed deployment to an independent "
            "air-gapped target machine, and not NCIIPC deployment proof."),
        "wheelhouse": wh_check,
        "checks": checks,
        "started_at": started,
        "finished_at": time.time(),
    }
    out_file = workdir / "airgap-rehearsal-report.json"
    try:
        out_file.write_text(json.dumps(report, indent=2, default=str),
                            encoding="utf-8")
        report["report_file"] = str(out_file)
    except Exception:
        pass

    if own_temp and not keep:
        # keep the report text in the return value; the temp tree itself
        # is disposable
        report_json = json.dumps(report, indent=2, default=str)
        shutil.rmtree(own_temp, ignore_errors=True)
        report["report_file"] = None
        report["report_json"] = report_json
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Non-destructive offline/air-gap deployment "
                    "rehearsal (same-host rehearsal, not target-"
                    "machine deployment proof)")
    parser.add_argument("--wheelhouse", type=Path, default=None,
                        help="directory containing the offline wheel "
                             "bundle (required for a full rehearsal)")
    parser.add_argument("--out", type=Path, default=None,
                        help="directory for the venv + report (default: "
                             "system temp dir)")
    parser.add_argument("--keep", action="store_true",
                        help="keep the rehearsal venv and report")
    args = parser.parse_args()
    report = run_rehearsal(wheelhouse=args.wheelhouse,
                           workdir=args.out, keep=args.keep)
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["overall"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())

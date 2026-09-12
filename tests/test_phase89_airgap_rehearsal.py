"""P33 — offline/air-gap rehearsal tool: safe failure and correct
command construction, proven without any network activity.

The tool must fail clearly when the deployment bundle is missing
("bundle not supplied"), never pretend success, and every install
command it would run must use --no-index with a local --find-links
wheelhouse. Full rehearsed installs (with a real wheelhouse) are
executed separately as evidence, not inside the unit suite.
"""
from __future__ import annotations

import json

import pytest

from scripts.airgap_rehearsal import (
    REPO_ROOT,
    _console_script,
    _runtime_requirement_names,
    _venv_python,
    check_wheelhouse,
    install_commands,
    run_rehearsal,
)


# ---------------------------------------------------------------------------
# Wheelhouse checks: fail clearly, never pretend
# ---------------------------------------------------------------------------

def test_missing_wheelhouse_path_reports_bundle_not_supplied(tmp_path):
    result = check_wheelhouse(tmp_path / "does-not-exist")
    assert result["status"] == "fail"
    assert any("bundle not supplied" in p for p in result["problems"])


def test_missing_wheelhouse_argument_reports_bundle_not_supplied():
    """No path at all — the tool must say what is missing, not skip
    silently or pretend the rehearsal succeeded."""
    report = run_rehearsal(wheelhouse=None)
    assert report["overall"] == "fail"
    present = next(c for c in report["checks"]
                   if c["name"] == "wheelhouse_present")
    assert present["status"] == "fail"
    assert "bundle not supplied" in present["detail"]


def test_empty_wheelhouse_directory_is_a_failure(tmp_path):
    empty = tmp_path / "empty-wheelhouse"
    empty.mkdir()
    result = check_wheelhouse(empty)
    assert result["status"] == "fail"
    assert "contains no .whl files" in result["problems"][0]


def test_missing_runtime_wheel_is_detected(tmp_path):
    """A bundle that lacks a wheel for a runtime requirement must be
    reported, wheel-by-wheel against requirements.txt's runtime
    section."""
    wh = tmp_path / "wh"
    wh.mkdir()
    (wh / "numpy-2.5.3-cp313-cp313-win_amd64.whl").write_bytes(b"x")
    reqs = tmp_path / "requirements.txt"
    reqs.write_text("numpy>=1.24\nhttpx>=0.27\n", encoding="utf-8")
    result = check_wheelhouse(wh, requirements_path=reqs)
    assert result["status"] == "fail"
    assert any("httpx" in p for p in result["problems"])
    assert not any("numpy" in p for p in result["problems"])


def test_missing_setuptools_wheel_warns_not_fails(tmp_path):
    """Python 3.12+ needs setuptools to build the project wheel; its
    absence is a warning (install may still be retried with a
    completed bundle), not a silent pass or a hard structural fail."""
    wh = tmp_path / "wh"
    wh.mkdir()
    reqs = tmp_path / "requirements.txt"
    reqs.write_text("httpx>=0.27\n", encoding="utf-8")
    (wh / "httpx-0.28.1-py3-none-any.whl").write_bytes(b"x")
    result = check_wheelhouse(wh, requirements_path=reqs)
    assert result["status"] == "warn"
    assert any("setuptools" in w for w in result["warnings"])


def test_runtime_requirement_parsing_skips_dev_section():
    names = _runtime_requirement_names(REPO_ROOT / "requirements.txt")
    assert "numpy" in names
    assert "pytest" not in names
    assert "httpx" not in names
    assert "setuptools" not in names


# ---------------------------------------------------------------------------
# Command construction: offline by construction
# ---------------------------------------------------------------------------

def test_install_commands_use_no_index_and_find_links(tmp_path):
    wh = tmp_path / "wh"
    wh.mkdir()
    py = tmp_path / "python.exe"
    cmds = install_commands(wh, REPO_ROOT, py)
    assert len(cmds) == 2
    for cmd in cmds:
        assert "--no-index" in cmd
        assert "--find-links" in cmd
        assert str(wh) in cmd
    # The project install itself uses --no-deps: requirements.txt has
    # already supplied every runtime dependency in the previous command.
    assert "--no-deps" in cmds[1]


def test_venv_and_console_script_paths_are_platform_correct(tmp_path):
    import os
    py = _venv_python(tmp_path)
    cli = _console_script(tmp_path, "sat-sa")
    if os.name == "nt":
        assert py.name == "python.exe"
        assert cli.name == "sat-sa.exe"
        assert py.parent.name == "Scripts"
    else:
        assert py.name == "python"
        assert cli.name == "sat-sa"
        assert py.parent.name == "bin"


def test_failed_rehearsal_report_is_structured_json_safe(tmp_path):
    """A failed rehearsal must still produce a well-formed structured
    report (machine-readable, with the honesty scope note), not raise
    or half-print success."""
    report = run_rehearsal(wheelhouse=None, workdir=tmp_path / "wd",
                           skip_heavy=True)
    assert report["overall"] == "fail"
    json.dumps(report)  # must be JSON-serializable
    assert report["scope_note"].startswith(
        "This is a same-host rehearsal")
    names = [c["name"] for c in report["checks"]]
    assert names == ["wheelhouse_present"]
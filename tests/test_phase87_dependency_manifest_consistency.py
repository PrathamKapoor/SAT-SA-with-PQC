"""P28 — dependency manifest reconciliation.

Verifies ``requirements.txt`` and ``pyproject.toml`` describe the same
runtime dependency contract, and that development-only dependencies
stay textually separated in ``requirements.txt`` rather than being
silently indistinguishable from runtime requirements.

This is a pure text/config comparison — no network access, no
comparison against what happens to be installed in the current
environment (that would make the test pass or fail based on this
machine's local site-packages, which is exactly the kind of
environment-dependent test this project's own testing discipline
avoids). It compares two committed, declared manifests to each other.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
REQUIREMENTS_PATH = REPO_ROOT / "requirements.txt"


def _load_pyproject() -> dict:
    try:
        import tomllib
    except ModuleNotFoundError:
        pytest.skip("tomllib unavailable (Python < 3.11)")
    with PYPROJECT_PATH.open("rb") as fh:
        return tomllib.load(fh)


def _parse_requirement_line(line: str) -> str:
    """Normalize a requirement line to 'name<specifier>' with no
    surrounding whitespace, lowercased package name (PEP 503-ish,
    good enough for exact-match comparison of this project's own two
    manifests)."""
    line = line.strip()
    m = re.match(r"^([A-Za-z0-9_.-]+)\s*(.*)$", line)
    assert m, f"unparseable requirement line: {line!r}"
    name, spec = m.group(1), m.group(2).strip()
    return f"{name.lower()}{spec}"


def _split_requirements_txt() -> tuple[set, set]:
    """Split requirements.txt into (runtime, dev) sets based on the
    '# Development' section marker. Blank lines and comments are
    skipped; every non-comment, non-blank line must fall on one side
    or the other."""
    text = REQUIREMENTS_PATH.read_text(encoding="utf-8")
    runtime: set = set()
    dev: set = set()
    in_dev_section = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            if "development" in line.lower() or "dev " in line.lower() or line.lower().startswith("# dev"):
                in_dev_section = True
            continue
        target = dev if in_dev_section else runtime
        target.add(_parse_requirement_line(line))
    return runtime, dev


def _pyproject_runtime_deps() -> set:
    data = _load_pyproject()
    return {_parse_requirement_line(d) for d in data["project"]["dependencies"]}


def _pyproject_dev_deps() -> set:
    data = _load_pyproject()
    dev = data["project"].get("optional-dependencies", {}).get("dev", [])
    return {_parse_requirement_line(d) for d in dev}


def test_requirements_txt_has_a_development_section_marker():
    """Development-only dependencies must be textually distinguishable
    from runtime ones in requirements.txt, not silently mixed in."""
    text = REQUIREMENTS_PATH.read_text(encoding="utf-8").lower()
    assert "development" in text or "# dev" in text, (
        "requirements.txt has no comment marker separating runtime "
        "from development/test-only dependencies")


def test_requirements_txt_runtime_section_matches_pyproject_dependencies():
    runtime_reqs, _ = _split_requirements_txt()
    pyproject_deps = _pyproject_runtime_deps()
    assert runtime_reqs == pyproject_deps, (
        f"requirements.txt's runtime section and pyproject.toml's "
        f"[project].dependencies have drifted.\n"
        f"Only in requirements.txt: {runtime_reqs - pyproject_deps}\n"
        f"Only in pyproject.toml:   {pyproject_deps - runtime_reqs}")


def test_requirements_txt_dev_section_matches_pyproject_dev_extra():
    _, dev_reqs = _split_requirements_txt()
    pyproject_dev = _pyproject_dev_deps()
    assert dev_reqs == pyproject_dev, (
        f"requirements.txt's development section and pyproject.toml's "
        f"[project.optional-dependencies].dev have drifted.\n"
        f"Only in requirements.txt: {dev_reqs - pyproject_dev}\n"
        f"Only in pyproject.toml:   {pyproject_dev - dev_reqs}")


def test_no_package_appears_in_both_runtime_and_dev_sections():
    """A package should have exactly one classification, not both --
    otherwise "clearly separated" is not actually true."""
    runtime_reqs, dev_reqs = _split_requirements_txt()
    runtime_names = {r.split(">=")[0].split("==")[0].split("<")[0] for r in runtime_reqs}
    dev_names = {r.split(">=")[0].split("==")[0].split("<")[0] for r in dev_reqs}
    assert runtime_names.isdisjoint(dev_names), (
        f"packages classified as both runtime and dev: "
        f"{runtime_names & dev_names}")


def test_pyproject_dependencies_and_dev_extra_are_disjoint():
    """Same invariant, checked against pyproject.toml directly (the
    authoritative source), independent of requirements.txt's own
    formatting."""
    runtime_names = {r.split(">=")[0] for r in _pyproject_runtime_deps()}
    dev_names = {r.split(">=")[0] for r in _pyproject_dev_deps()}
    assert runtime_names.isdisjoint(dev_names)

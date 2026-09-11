"""Release-readiness correction (P26/P27 packaging fix) — verifies
``pyproject.toml``'s package discovery actually includes every
first-party package the CLI and benchmark tooling need at runtime.

Real bug this closes: `[tool.setuptools.packages.find]` previously
declared `include = ["qsmlops*", "satsa*"]` only. `sat-sa ablate`
(`satsa/cli.py::cmd_ablate`) imports `evaluation.ablation.runner` at
call time, and `public_benchmarks/` was entirely absent from the
distributable package set — a `pip install` from an sdist/wheel built
under the old config would omit both packages, and `sat-sa ablate`
would fail with `ModuleNotFoundError` in that installed environment
even though it works from this source checkout (where the whole repo
root is importable directly, masking the bug).

This test verifies the *discovery configuration* using the real
`setuptools` discovery function the build backend actually calls —
not a hand-parsed guess at what it would find — so it fails the same
way a real `pip install .` would if the config regressed. It does not
perform a network install (no PyPI access, no isolated venv build);
see ``docs/roadmap-status.md``'s release-readiness correction entry
for why a full isolated-install test was not attempted in this
environment.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"

REQUIRED_PACKAGE_PREFIXES = ("qsmlops", "satsa", "evaluation", "public_benchmarks")


def _load_pyproject() -> dict:
    try:
        import tomllib
    except ModuleNotFoundError:
        pytest.skip("tomllib unavailable (Python < 3.11) -- see module docstring")
    with PYPROJECT_PATH.open("rb") as fh:
        return tomllib.load(fh)


def test_pyproject_declares_all_four_first_party_package_prefixes():
    data = _load_pyproject()
    include = data["tool"]["setuptools"]["packages"]["find"]["include"]
    for prefix in REQUIRED_PACKAGE_PREFIXES:
        assert f"{prefix}*" in include, (
            f"{prefix}* missing from [tool.setuptools.packages.find].include "
            f"-- a built wheel/sdist would omit the {prefix} package")


def test_setuptools_discovery_actually_finds_evaluation_and_public_benchmarks():
    """Runs the real setuptools discovery logic (the same function the
    build backend calls) against this repo, using the include patterns
    read from pyproject.toml itself -- not a hardcoded duplicate list
    that could silently drift from the real config."""
    from setuptools import find_packages

    data = _load_pyproject()
    include = data["tool"]["setuptools"]["packages"]["find"]["include"]
    discovered = find_packages(where=str(REPO_ROOT), include=include)

    for prefix in REQUIRED_PACKAGE_PREFIXES:
        assert prefix in discovered, (
            f"setuptools.find_packages(include={include!r}) did not "
            f"discover the {prefix!r} top-level package")

    # sat-sa ablate's actual import target, and the two public_benchmarks
    # sub-packages the adapters live in -- must all be discoverable, not
    # just the top-level namespace.
    for required in ("evaluation.ablation", "evaluation.baselines",
                     "public_benchmarks.bots", "public_benchmarks.cicids2017",
                     "public_benchmarks.workflow_augmentation"):
        assert required in discovered, (
            f"setuptools.find_packages(include={include!r}) did not "
            f"discover {required!r} -- sat-sa ablate / the public "
            "benchmark adapters would not be importable from an "
            "installed distribution")


def test_cmd_ablate_import_target_is_importable_from_this_source_tree():
    """Confirms the actual module sat-sa ablate imports
    (satsa/cli.py::cmd_ablate does `from evaluation.ablation.runner
    import run_ablation_study`) exists and imports cleanly from this
    checkout. This does NOT prove an installed (pip-built) environment
    would succeed -- only the discovery-configuration tests above
    establish that; this test guards against the import target itself
    being renamed/removed without the CLI being updated to match."""
    from evaluation.ablation.runner import run_ablation_study  # noqa: F401

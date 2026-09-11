"""Deployment environment validation (Phase 6).

Compares what a model DECLARED about its runtime (passport environment,
QML-BOM dependency/hardware entries) against what the target host actually
exposes. The validator never fabricates capabilities: anything it cannot
measure is reported explicitly as UNVERIFIABLE and surfaced to the caller
instead of being silently treated as compatible.

A report is `compatible` only when no check returned MISMATCH. UNVERIFIABLE
checks degrade confidence but do not claim compatibility.
"""
from __future__ import annotations

import importlib.metadata
import platform
from dataclasses import dataclass, field

OK = "OK"
MISMATCH = "MISMATCH"
UNVERIFIABLE = "UNVERIFIABLE"


@dataclass
class EnvCheck:
    name: str
    declared: str
    actual: str
    status: str
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "declared": self.declared,
            "actual": self.actual,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass
class EnvironmentReport:
    target_environment: str
    checks: list[EnvCheck] = field(default_factory=list)

    @property
    def compatible(self) -> bool:
        return all(c.status != MISMATCH for c in self.checks)

    @property
    def unverified(self) -> list[str]:
        return [c.name for c in self.checks if c.status == UNVERIFIABLE]

    def to_dict(self) -> dict:
        return {
            "target_environment": self.target_environment,
            "compatible": self.compatible,
            "checks": [c.to_dict() for c in self.checks],
            "unverifiable": self.unverified,
        }


def _python_family(version: str) -> tuple[int, int] | None:
    parts = version.split(".")
    try:
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return None


def validate_environment(passport, bom, target_environment: str) -> EnvironmentReport:
    """Validate declared model requirements against the local runtime."""
    report = EnvironmentReport(target_environment=target_environment)
    env = (getattr(passport, "environment", {}) or {}) if passport is not None else {}
    training_info = (getattr(passport, "training_info", {}) or {}) if passport is not None else {}

    # ---- Python runtime compatibility ---------------------------------
    declared_python = str(env.get("python", "") or "")
    actual_python = platform.python_version()
    declared_family = _python_family(declared_python)
    if not declared_python:
        report.checks.append(EnvCheck(
            "python_runtime", "", actual_python, UNVERIFIABLE,
            "passport declares no python version; compatibility not verified",
        ))
    elif declared_python == actual_python:
        report.checks.append(EnvCheck(
            "python_runtime", declared_python, actual_python, OK,
            "exact interpreter match",
        ))
    elif declared_family == _python_family(actual_python):
        report.checks.append(EnvCheck(
            "python_runtime", declared_python, actual_python, OK,
            "same major.minor runtime family",
        ))
    else:
        report.checks.append(EnvCheck(
            "python_runtime", declared_python, actual_python, MISMATCH,
            f"model requires python {declared_python}; host runs {actual_python}",
        ))

    # ---- Third-party dependencies (QML-BOM dependency entries) --------
    framework = str(training_info.get("framework", "reference") or "reference")
    deps = bom.by_kind("dependency") if bom is not None else []
    if framework == "reference":
        report.checks.append(EnvCheck(
            "framework_dependencies", "none (pure-python reference trainer)",
            "stdlib only", OK, "reference trainer has no third-party requirements",
        ))
    elif not deps:
        report.checks.append(EnvCheck(
            "framework_dependencies", framework, "?", UNVERIFIABLE,
            "non-reference model declared no dependency entries; "
            "compatibility cannot be verified from the BOM",
        ))
    else:
        for entry in deps:
            try:
                installed = importlib.metadata.version(entry.name)
            except importlib.metadata.PackageNotFoundError:
                installed = ""
            declared_version = entry.version or "?"
            if installed == entry.version and installed:
                report.checks.append(EnvCheck(
                    f"dependency:{entry.name}", declared_version, installed, OK,
                    "installed version matches the declared BOM pin",
                ))
            elif not installed:
                report.checks.append(EnvCheck(
                    f"dependency:{entry.name}", declared_version, "not installed",
                    MISMATCH, f"declared {entry.name}=={declared_version} is absent on host",
                ))
            else:
                report.checks.append(EnvCheck(
                    f"dependency:{entry.name}", declared_version, installed, MISMATCH,
                    f"host has {entry.name}=={installed}, model was validated with {declared_version}",
                ))

    # ---- Hardware ------------------------------------------------------
    declared_hw = str(env.get("hardware", "") or "")
    if declared_hw.lower() == "cpu":
        report.checks.append(EnvCheck(
            "hardware", declared_hw or "unspecified", "cpu host", OK,
            "cpu-only workload served on cpu host",
        ))
    else:
        report.checks.append(EnvCheck(
            "hardware", declared_hw or "unspecified", "unmeasured", UNVERIFIABLE,
            "accelerator availability cannot be inspected by this validator",
        ))

    return report

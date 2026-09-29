#!/usr/bin/env python3
"""Summarize Trivy JSON reports so findings are readable without downloading artifacts.

Usage: summarize_trivy.py REPORT.json [REPORT.json ...]

Writes a Markdown table to $GITHUB_STEP_SUMMARY (when set), prints the same
table, and emits GitHub annotations (public through the checks API) so the
HIGH and CRITICAL findings survive log expiry and need no authentication to
read. It never changes the scan's exit status; the gate lives in the workflow.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SEVERITIES = ("CRITICAL", "HIGH")
CHUNK = 3200  # annotation messages are size-limited
MAX_ANNOTATIONS = 9  # GitHub shows at most 10 per type per step


def findings(path: Path) -> list[dict]:
    report = json.loads(path.read_text())
    image = report.get("ArtifactName", path.stem)
    rows = []
    for result in report.get("Results") or []:
        kind = result.get("Class", "")  # os-pkgs | lang-pkgs
        for vuln in result.get("Vulnerabilities") or []:
            if vuln.get("Severity") not in SEVERITIES:
                continue
            rows.append(
                {
                    "image": image,
                    "target": result.get("Target", ""),
                    "class": kind,
                    "id": vuln.get("VulnerabilityID", ""),
                    "pkg": vuln.get("PkgName", ""),
                    "installed": vuln.get("InstalledVersion", ""),
                    "fixed": vuln.get("FixedVersion") or "-",
                    "severity": vuln.get("Severity", ""),
                    "title": (vuln.get("Title") or "")[:90],
                }
            )
    rows.sort(key=lambda r: (r["severity"] != "CRITICAL", r["fixed"] == "-", r["image"], r["pkg"]))
    return rows


def main(argv: list[str]) -> int:
    rows = [row for arg in argv for row in findings(Path(arg))]
    header = "| Image | Vulnerability | Package | Installed | Fixed | Severity | Class | Target |\n|---|---|---|---|---|---|---|---|"
    table = [
        f"| {r['image']} | {r['id']} | {r['pkg']} | {r['installed']} | {r['fixed']} | {r['severity']} | {r['class']} | {r['target']} |"
        for r in rows
    ]
    text = f"### Trivy HIGH/CRITICAL findings ({len(rows)})\n\n{header}\n" + "\n".join(table) + "\n"
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(text)

    lines = [
        f"{r['image']}|{r['severity']}|{r['id']}|{r['pkg']} {r['installed']}>{r['fixed']}|{r['class']}"
        for r in rows
    ]
    chunks, current = [], ""
    for line in lines:
        if len(current) + len(line) + 1 > CHUNK:
            chunks.append(current)
            current = ""
        current += line + "\n"
    if current:
        chunks.append(current)
    if not chunks:
        print("::notice title=trivy::no HIGH or CRITICAL findings in any scanned image")
    for index, chunk in enumerate(chunks[:MAX_ANNOTATIONS], 1):
        body = chunk.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::warning title=trivy findings {index}/{len(chunks)}::{body}")
    if len(chunks) > MAX_ANNOTATIONS:
        print(f"::warning title=trivy findings truncated::{len(chunks) - MAX_ANNOTATIONS} more chunks; see image-scan-report artifact")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Phase 20K: no credential-shaped material is tracked in the repository.

This is a pattern check over git-tracked files, not a replacement for a
history scanner; it guards against the common accident of committing a
private key, cloud access key or personal access token.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

PATTERNS = {
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "AWS access key id": re.compile(r"AKIA[0-9A-Z]{16}"),
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "Slack token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    "Google API key": re.compile(r"AIza[0-9A-Za-z_-]{35}"),
}
FORBIDDEN_TRACKED = re.compile(r"(^|/)(\.env|credentials\.json|.*\.pem|.*\.key)$")
ALLOWED_TRACKED = {".env.saas.example"}
MAX_BYTES = 2_000_000


def _tracked() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return [p for p in out.decode().split("\0") if p]


def test_no_credential_files_are_tracked():
    bad = [
        p
        for p in _tracked()
        if FORBIDDEN_TRACKED.search(p) and Path(p).name not in ALLOWED_TRACKED
    ]
    assert not bad, f"credential-style files are tracked: {bad}"


def test_no_credential_patterns_in_tracked_text():
    hits: list[str] = []
    for rel in _tracked():
        path = ROOT / rel
        if not path.is_file() or path.stat().st_size > MAX_BYTES:
            continue
        data = path.read_bytes()
        if b"\0" in data[:4096]:
            continue
        text = data.decode("utf-8", errors="ignore")
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                hits.append(f"{rel}: {label}")
    assert not hits, f"credential-shaped material in tracked files: {hits}"

"""Phase 22: the hosted deployment target is AWS (deploy/aws). Render hosting
was removed in Phase 15 and again in Phase 22 after it was re-added by
accident; these checks stop it from returning silently."""

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PATHS = ("render.yaml", "render.yml", "deploy/render/", "scripts/render_stack.py")
# Operational references to Render hosting (not the English verb).
FORBIDDEN_TEXT = re.compile(r"onrender\.com|dashboard\.render\.com|RENDER_EXTERNAL_URL|render_stack")
# Historical records may mention the old prototype URL.
HISTORY = ("docs/SAAS_BACKEND_DISCOVERY.md", "docs/FRONTEND_BACKEND_CONVERGENCE.md",
           "tests/test_phase22_no_render.py")


def _tracked() -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return [p for p in out.decode().split("\0") if p]


def test_no_render_deployment_files_are_tracked():
    tracked = _tracked()
    bad = [p for p in tracked if p.startswith(FORBIDDEN_PATHS) or p in FORBIDDEN_PATHS]
    assert not bad, f"Render deployment files are tracked: {bad}"


def test_no_render_hosting_references_outside_history():
    hits = []
    for rel in _tracked():
        if rel in HISTORY or not rel.endswith((".py", ".yml", ".yaml", ".ts", ".tsx", ".sh", ".md",
                                               ".json", ".toml", ".caddy", "Dockerfile")):
            continue
        path = ROOT / rel
        if path.is_file() and path.stat().st_size < 2_000_000 and FORBIDDEN_TEXT.search(
                path.read_text("utf-8", errors="ignore")):
            hits.append(rel)
    assert not hits, f"Render hosting references: {hits}"

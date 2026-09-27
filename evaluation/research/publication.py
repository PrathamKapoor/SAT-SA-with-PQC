"""Write-once publication snapshot: the manuscript package bound to a freeze.

A snapshot copies the publication files (manuscript, sections, generated
data, tables, figures, supplementary material, literature matrix and
bibliography) and records their SHA-256 values together with the evidence
freeze they were generated from (freeze id and ``freeze.json`` hash), the
commit that contains the paper, the dataset versions and the environment.
Verification recomputes every hash and re-verifies the referenced freeze.
"""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evaluation.research.freeze import verify_freeze

SCHEMA = "satsa-publication/1"
# Paths under paper/ included in a snapshot; LaTeX build intermediates are not.
INCLUDE = (
    "manuscript.tex",
    "manuscript.pdf",
    "references.bib",
    "literature-matrix.csv",
    "REPRODUCIBILITY.md",
    "sections",
    "tables",
    "figures",
    "data",
    "supplementary",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _package_files(paper_dir: Path) -> list[Path]:
    files: list[Path] = []
    for name in INCLUDE:
        path = paper_dir / name
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(p for p in sorted(path.rglob("*")) if p.is_file())
        else:
            raise FileNotFoundError(f"publication file missing: {path}")
    return files


def build_publication(
    paper_dir: Path,
    freeze_dir: Path,
    out_dir: Path,
    *,
    publication_id: str,
    paper_commit: str,
    manuscript_version: str,
    literature_snapshot_date: str,
) -> dict[str, Any]:
    """Copy the package into a new directory and write publication.json."""
    paper_dir, freeze_dir, out_dir = Path(paper_dir), Path(freeze_dir), Path(out_dir)
    if out_dir.exists():
        raise FileExistsError(f"{out_dir} exists; publication snapshots are write-once")
    freeze = verify_freeze(freeze_dir)
    if not freeze["intact"]:
        raise ValueError(f"freeze {freeze_dir} is not intact: {freeze['problems']}")
    record = json.loads((freeze_dir / "freeze.json").read_text(encoding="utf-8"))
    files: dict[str, str] = {}
    for source in _package_files(paper_dir):
        rel = source.relative_to(paper_dir).as_posix()
        target = out_dir / "paper" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        files[f"paper/{rel}"] = _sha256(target)
    datasets = sorted(
        {
            f"{b['dataset'].get('id')} {b['dataset'].get('version')}"
            for b in record["bundles"]
            if b["role"] == "canonical"
        }
    )
    publication = {
        "schema": SCHEMA,
        "publication_id": publication_id,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "freeze": {
            "freeze_id": record["freeze_id"],
            "path": freeze_dir.as_posix(),
            "freeze_json_sha256": _sha256(freeze_dir / "freeze.json"),
            "canonical_code_commit": record.get("canonical_code_commit"),
        },
        "paper_commit": paper_commit,
        "manuscript_version": manuscript_version,
        "dataset_versions": datasets,
        "literature_snapshot_date": literature_snapshot_date,
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "verification": "python scripts/build_publication_snapshot.py --verify <dir>",
        "files": files,
    }
    (out_dir / "publication.json").write_text(
        json.dumps(publication, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return publication


def verify_publication(pub_dir: Path, *, repo_root: Path | None = None) -> dict[str, Any]:
    """Recompute file hashes and re-verify the referenced evidence freeze."""
    pub_dir = Path(pub_dir)
    record = json.loads((pub_dir / "publication.json").read_text(encoding="utf-8"))
    problems: list[str] = []
    for rel, expected in sorted(record["files"].items()):
        path = pub_dir / rel
        if not path.is_file():
            problems.append(f"missing {rel}")
        elif _sha256(path) != expected:
            problems.append(f"hash mismatch {rel}")
    listed = set(record["files"])
    for path in sorted((pub_dir / "paper").rglob("*")):
        rel = path.relative_to(pub_dir).as_posix()
        if path.is_file() and rel not in listed:
            problems.append(f"unlisted file {rel}")
    freeze_dir = Path(repo_root or Path.cwd()) / record["freeze"]["path"]
    if not (freeze_dir / "freeze.json").is_file():
        problems.append(f"referenced freeze not found: {freeze_dir}")
    else:
        if _sha256(freeze_dir / "freeze.json") != record["freeze"]["freeze_json_sha256"]:
            problems.append("freeze.json hash differs from the recorded value")
        freeze = verify_freeze(freeze_dir)
        if not freeze["intact"]:
            problems.append(f"freeze not intact: {freeze['problems']}")
    return {
        "publication_id": record["publication_id"],
        "freeze_id": record["freeze"]["freeze_id"],
        "files_checked": len(record["files"]),
        "intact": not problems,
        "problems": problems,
    }

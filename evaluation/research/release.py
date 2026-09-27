"""Submission release candidate: assemble, validate by compiling, and manifest.

The release candidate is a clean copy of the venue package (paper/submission)
with build intermediates, audit-only files and development files removed. It is
validated by compiling the copy itself in an isolated directory, and described by
a manifest (file, SHA-256, size, purpose, origin, source commit).
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = "satsa-release-candidate/1"
# Top-level entries of paper/submission copied into the release candidate.
INCLUDE = (
    "manuscript.tex",
    "manuscript.pdf",
    "references.bib",
    "sections",
    "data",
    "tables",
    "figures",
    "figures-static",
    "figures-src",
    "supplementary",
    "README.md",
    "cover-letter.md",
    "AUTHOR_INPUT_REQUIRED.md",
    "author-inputs.json",
    "REPRODUCIBILITY_STATUS.md",
)
# IEEE Access template files needed to compile (copied unmodified).
TEMPLATE_PATTERNS = (
    "*.cls",
    "*.bst",
    "*.sty",
    "*.fd",
    "*.tfm",
    "*.pfb",
    "*.map",
    "*.png",
)
EXCLUDED_SUFFIXES = (
    ".aux",
    ".bbl",
    ".blg",
    ".fdb_latexmk",
    ".fls",
    ".log",
    ".out",
    ".synctex.gz",
    ".pyc",
    ".bak",
    "~",
)
EXCLUDED_NAMES = {"__pycache__", ".DS_Store", "Thumbs.db"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _excluded(path: Path) -> bool:
    return any(part in EXCLUDED_NAMES for part in path.parts) or path.name.endswith(
        EXCLUDED_SUFFIXES
    )


def _purpose(rel: str) -> tuple[str, str]:
    """(purpose, generated_from) for a release-candidate path."""
    rules = [
        ("manuscript.pdf", "compiled manuscript", "manuscript.tex (pdflatex + bibtex)"),
        (
            "manuscript.tex",
            "manuscript source (IEEE Access wrapper)",
            "paper/venue/ieee-access-manuscript.tex",
        ),
        (
            "references.bib",
            "bibliography",
            "paper/references.bib (verified in paper/literature-matrix.csv)",
        ),
        (
            "sections/",
            "manuscript body text",
            "paper/sections (hand-written; numbers via \\V)",
        ),
        (
            "data/",
            "paper values and provenance",
            "research/evidence/freeze-v2 via scripts/build_paper_assets.py",
        ),
        (
            "tables/",
            "manuscript table",
            "research/evidence/freeze-v2 via scripts/build_paper_assets.py",
        ),
        (
            "figures/",
            "manuscript figure",
            "research/evidence/freeze-v2 via scripts/build_paper_assets.py",
        ),
        (
            "figures-static/",
            "Figure 1 (architecture)",
            "paper/figures-src/fig-architecture.tex",
        ),
        (
            "figures-src/",
            "Figure 1 source",
            "hand-written TikZ; code facts from data/values.tex",
        ),
        (
            "supplementary/generated/",
            "supplementary material",
            "research/evidence/freeze-v2 via scripts/build_paper_assets.py",
        ),
        (
            "supplementary/literature-review/",
            "supplementary material (literature search)",
            "paper/literature-review",
        ),
        ("supplementary/", "supplementary material", "paper/supplementary"),
        ("README.md", "package description", "hand-written"),
        (
            "cover-letter.md",
            "cover letter draft",
            "hand-written; author fields pending",
        ),
        ("AUTHOR_INPUT_REQUIRED.md", "author input checklist", "hand-written"),
        (
            "author-inputs.json",
            "author input status (machine-readable)",
            "hand-written",
        ),
        ("REPRODUCIBILITY_STATUS.md", "reproducibility status", "hand-written"),
        (
            "VENUE_COMPLIANCE.md",
            "venue compliance checklist",
            "paper/VENUE_COMPLIANCE.md",
        ),
    ]
    for prefix, purpose, origin in rules:
        if rel == prefix or (prefix.endswith("/") and rel.startswith(prefix)):
            return purpose, origin
    return (
        "IEEE Access template file",
        "official IEEE Access LaTeX template 2026-05-13 (unmodified)",
    )


def git_state(repo: Path, exclude: Path | None = None) -> dict[str, Any]:
    """HEAD and whether the paper sources differ from it (the output dir excluded)."""

    def run(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True, check=True
        ).stdout.strip()

    specs = ["paper", "evaluation", "scripts"]
    if exclude is not None:
        specs.append(f":(exclude){Path(exclude).as_posix()}")
    dirty = run("status", "--porcelain", "--", *specs)
    return {"commit": run("rev-parse", "HEAD"), "paper_tree_dirty": bool(dirty)}


def assemble(submission: Path, compliance: Path, out: Path) -> list[Path]:
    """Copy the allowed package files into a fresh release-candidate directory."""
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for name in INCLUDE:
        source = submission / name
        if source.is_dir():
            for f in sorted(source.rglob("*")):
                if f.is_file() and not _excluded(f.relative_to(submission)):
                    target = out / f.relative_to(submission)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, target)
        elif source.is_file():
            shutil.copy2(source, out / name)
        else:
            raise FileNotFoundError(f"release file missing: {source}")
    for pattern in TEMPLATE_PATTERNS:
        for f in sorted(submission.glob(pattern)):
            shutil.copy2(f, out / f.name)
    shutil.copy2(compliance, out / "VENUE_COMPLIANCE.md")
    return sorted(p for p in out.rglob("*") if p.is_file())


def _referenced_assets(tex_root: Path) -> list[str]:
    """Paths the manuscript inputs or includes, relative to the package root."""
    refs: list[str] = []
    texts = [
        tex_root / "manuscript.tex",
        *sorted((tex_root / "sections").glob("*.tex")),
    ]
    pattern = re.compile(
        r"\\(?:input|widetable|includegraphics(?:\[[^\]]*\])?)\{([^}]+)\}"
    )
    for tex in texts:
        body = re.sub(r"(?m)(?<!\\)%.*$", "", tex.read_text(encoding="utf-8"))
        for ref in pattern.findall(body):
            if "#" in ref:
                continue
            candidates = [ref, f"{ref}.tex"]
            refs.append(next((c for c in candidates if (tex_root / c).is_file()), ref))
    return refs


def validate(rc: Path, *, compile_pdf: bool = True) -> dict[str, Any]:
    """Check assets and compile an isolated copy of the release candidate."""
    problems: list[str] = []
    for rel in _referenced_assets(rc):
        if not (rc / rel).is_file():
            problems.append(f"missing asset {rel}")
    stray = [
        p.relative_to(rc).as_posix()
        for p in rc.rglob("*")
        if p.is_file() and _excluded(p)
    ]
    problems += [f"build or development file in package: {s}" for s in stray]
    result: dict[str, Any] = {"assets_checked": len(_referenced_assets(rc))}
    if compile_pdf:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "rc"
            shutil.copytree(rc, work)
            (work / "manuscript.pdf").unlink(missing_ok=True)
            steps = [
                ["pdflatex", "-interaction=nonstopmode", "manuscript.tex"],
                ["bibtex", "manuscript"],
                ["pdflatex", "-interaction=nonstopmode", "manuscript.tex"],
                ["pdflatex", "-interaction=nonstopmode", "manuscript.tex"],
            ]
            for cmd in steps:
                subprocess.run(
                    cmd, cwd=work, capture_output=True, text=True, check=False
                )
            log = (work / "manuscript.log").read_text(encoding="latin-1")
            errors = [line for line in log.splitlines() if line.startswith("!")]
            undefined = re.findall(r"(?:Citation|Reference) `([^']+)' .*undefined", log)
            missing = re.findall(r"File `([^']+)' not found", log)
            pages = re.search(r"Output written on manuscript\.pdf \((\d+) pages?", log)
            problems += [f"latex error: {e}" for e in errors]
            problems += [f"undefined citation/reference: {u}" for u in undefined]
            problems += [f"missing file: {m}" for m in missing]
            if not pages:
                problems.append("no PDF produced")
            result.update(
                compiled=bool(pages),
                pages=int(pages.group(1)) if pages else None,
                latex_errors=len(errors),
                undefined_references=len(undefined),
            )
    result["problems"] = problems
    result["ok"] = not problems
    return result


def manifest(rc: Path, git: dict[str, Any]) -> dict[str, Any]:
    files = []
    for f in sorted(
        p for p in rc.rglob("*") if p.is_file() and p.name != "MANIFEST.json"
    ):
        rel = f.relative_to(rc).as_posix()
        purpose, origin = _purpose(rel)
        files.append(
            {
                "file": rel,
                "sha256": _sha256(f),
                "size": f.stat().st_size,
                "purpose": purpose,
                "generated_from": origin,
                "source_commit": git["commit"],
            }
        )
    return {
        "schema": SCHEMA,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "source_commit": git["commit"],
        "paper_tree_dirty": git["paper_tree_dirty"],
        "files": files,
    }


def release_record(
    repo: Path,
    rc: Path,
    manifest_record: dict[str, Any],
    validation: dict[str, Any],
    audits: dict[str, Any],
    *,
    venue: str,
    article_type: str,
    freeze: str,
    publication: str,
) -> dict[str, Any]:
    by_prefix = {m["file"]: m["sha256"] for m in manifest_record["files"]}

    def group(prefix: str) -> dict[str, str]:
        return {k: v for k, v in by_prefix.items() if k.startswith(prefix)}

    inputs = json.loads((rc / "author-inputs.json").read_text(encoding="utf-8"))
    open_inputs = [i["field"] for i in inputs["fields"] if i["status"] != "PROVIDED"]
    technical_ok = validation["ok"] and all(a.get("ok") for a in audits.values())
    return {
        "schema": "satsa-submission-release/1",
        "venue": venue,
        "article_type": article_type,
        "article_type_status": "AUTHOR CONFIRMATION REQUIRED",
        "source_commit": manifest_record["source_commit"],
        "paper_tree_dirty": manifest_record["paper_tree_dirty"],
        "build_date_utc": manifest_record["created_at_utc"],
        "manuscript": {
            "pdf_sha256": by_prefix.get("manuscript.pdf"),
            "tex_sha256": by_prefix.get("manuscript.tex"),
            "pages": validation.get("pages"),
        },
        "references_sha256": by_prefix.get("references.bib"),
        "figures": group("figures/") | group("figures-static/"),
        "tables": group("tables/"),
        "supplementary": group("supplementary/"),
        "release_candidate_manifest_sha256": _sha256(rc / "MANIFEST.json"),
        "freeze": {
            "path": freeze,
            "freeze_json_sha256": _sha256(repo / freeze / "freeze.json"),
        },
        "publication_snapshot": {
            "path": publication,
            "publication_json_sha256": _sha256(repo / publication / "publication.json"),
        },
        "verification": {
            "release_candidate_compile": validation,
            "audits": audits,
            "technical_checks_pass": technical_ok,
        },
        "author_inputs_open": open_inputs,
        "submission_ready": technical_ok and not open_inputs,
    }

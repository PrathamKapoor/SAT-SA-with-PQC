"""Build and validate the self-contained Springer/Overleaf project.

    python paper/build_overleaf.py

Source of truth: paper/springer-src (text with \\V{claim-id} macros),
paper/data/values.tex (values generated from research/evidence/freeze-v2),
paper/references.bib, paper/figures, and the vendored official Springer
template (paper/venue/springer-template). Output: paper/overleaf-springer/ with
every \\V resolved to its literal frozen value (so the project compiles and is
editable in Overleaf without this repository), CLAIM_TRACE.csv mapping each
resolved value back to its claim and experiment, MANIFEST.json, version.json,
main.pdf, and paper/overleaf-springer.zip. The Overleaf project never needs
this script; it only generates and validates the package.
"""

from __future__ import annotations

# ruff: noqa: C408  (keyword dict() calls mirror CSV/JSON field names)
import csv
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any

PAPER = Path(__file__).resolve().parent
ROOT = PAPER.parent
SRC = PAPER / "springer-src"
OUT = PAPER / "overleaf-springer"
ZIP = PAPER / "overleaf-springer.zip"
TEMPLATE = PAPER / "venue" / "springer-template"
FIGURES = [
    "fig-prioritization.pdf",
    "fig-robustness.pdf",
    "fig-peer.pdf",
    "fig-external.pdf",
]
BUILD_JUNK = (
    ".aux",
    ".log",
    ".synctex.gz",
    ".fls",
    ".fdb_latexmk",
    ".out",
    ".toc",
    ".blg",
    ".bbl",
)
# Filesystem-path leaks. "TRUST-SAT" is also the name of the integrity layer in the
# paper text, so only its use as a path segment is forbidden.
FORBIDDEN = [r"(?<![A-Za-z])[A-Za-z]:[\\/]", r"/mnt/data", r"TRUST-SAT[/\\]"]
REPO_ONLY = {
    "SOURCE_MAP.md",
    "CLAIM_TRACE.csv",
    "MANIFEST.json",
    "version.json",
    "main.pdf",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_values() -> dict[str, str]:
    """Parse \\@namedef{pv@ID}{VALUE} (VALUE may contain nested braces)."""
    text = (PAPER / "data" / "values.tex").read_text("utf-8")
    values: dict[str, str] = {}
    for m in re.finditer(r"\\@namedef\{pv@([^}]+)\}\{", text):
        depth, i = 1, m.end()
        while depth:
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        values[m.group(1)] = text[m.end() : i - 1]
    return values


def resolve(
    text: str,
    values: dict[str, str],
    rel: str,
    trace: list[dict[str, Any]],
    claims: dict[str, Any],
) -> str:
    def sub(m: re.Match[str]) -> str:
        key = m.group(1)
        if key not in values:
            raise SystemExit(f"undefined claim {key} in {rel}")
        line = text.count("\n", 0, m.start()) + 1
        c = claims.get(key, {})
        trace.append(
            dict(
                file=rel,
                source_line=line,
                claim_id=key,
                value=values[key],
                experiment=c.get("experiment_id"),
                source=str(c.get("source", ""))[:160],
            )
        )
        return values[key]

    return re.sub(r"\\V\{([^}]+)\}", sub, text)


def cited_keys(tex_files: list[Path]) -> set[str]:
    keys: set[str] = set()
    for f in tex_files:
        body = re.sub(r"(?m)(?<!\\)%.*$", "", f.read_text("utf-8"))
        for group in re.findall(r"\\cite\{([^}]+)\}", body):
            keys.update(k.strip() for k in group.split(","))
    return keys


def bib_subset(keys: set[str]) -> str:
    bib = (PAPER / "references.bib").read_text("utf-8")
    entries = {m.group(1): m for m in re.finditer(r"@\w+\{([^,\s]+),", bib)}
    missing = keys - set(entries)
    if missing:
        raise SystemExit(f"cited but not in references.bib: {sorted(missing)}")
    starts = sorted(m.start() for m in entries.values()) + [len(bib)]
    out = ["% Cited entries of the SAT-SA verified bibliography (see README.md).\n"]
    for key in sorted(keys):
        s = entries[key].start()
        e = next(x for x in starts if x > s)
        chunk = bib[s:e]
        chunk = chunk[: chunk.rfind("}") + 1]
        out.append(chunk + "\n")
    return "\n".join(out)


def compile_dir(workdir: Path) -> dict[str, Any]:
    for cmd in (
        ["pdflatex", "-interaction=nonstopmode", "main.tex"],
        ["bibtex", "main"],
        ["pdflatex", "-interaction=nonstopmode", "main.tex"],
        ["pdflatex", "-interaction=nonstopmode", "main.tex"],
    ):
        subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, check=False)
    log = (workdir / "main.log").read_text(encoding="latin-1")
    blg = (
        (workdir / "main.blg").read_text(encoding="latin-1")
        if (workdir / "main.blg").exists()
        else ""
    )
    pages = re.search(r"Output written on main\.pdf \((\d+) pages?", log)
    return dict(
        compiled=bool(pages),
        pages=int(pages.group(1)) if pages else None,
        errors=sum(1 for ln in log.splitlines() if ln.startswith("!")),
        undefined_refs=len(re.findall(r"Reference `[^']+' .*undefined", log)),
        undefined_citations=len(re.findall(r"Citation `[^']+' .*undefined", log))
        + blg.count("Warning--I didn't find"),
        missing_files=len(re.findall(r"File `[^']+' not found|No file main\.bbl", log)),
        overfull=len(re.findall(r"Overfull \\hbox", log)),
    )


def audit_source(claims_data: dict[str, Any]) -> list[str]:
    import sys

    sys.path.insert(0, str(ROOT))
    from evaluation.research.paper import audit_manuscript
    from evaluation.research.paper_audit import PROHIBITED

    tex = sorted(SRC.rglob("*.tex"))
    result = audit_manuscript(tex, claims_data)
    problems = [f"undefined claim {u}" for u in result["undefined"]]
    problems += [f"typed decimal {t}" for t in result["typed_decimals"]]
    patterns = {k: re.compile(v, re.IGNORECASE) for k, v in PROHIBITED.items()}
    for f in tex:
        for n, line in enumerate(f.read_text("utf-8").splitlines(), 1):
            text = re.split(r"(?<!\\)%", line, maxsplit=1)[0]
            problems += [
                f"prohibited wording '{k}' {f.name}:{n}"
                for k, p in patterns.items()
                if p.search(text)
            ]
    with (PAPER / "literature-matrix.csv").open(encoding="utf-8", newline="") as fh:
        verified = {
            r["key"]
            for r in csv.DictReader(fh)
            if r.get("source_url") and r.get("verified_via")
        }
    problems += [
        f"citation not a verified matrix row: {k}"
        for k in sorted(cited_keys(tex) - verified)
    ]
    AUDIT["claims_used"] = len(result["used"])
    return problems


AUDIT: dict[str, Any] = {}


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "sections").mkdir(parents=True)
    (OUT / "tables").mkdir()
    (OUT / "figures").mkdir()
    values = load_values()
    claims_data = json.loads((PAPER / "data" / "paper-data.json").read_text("utf-8"))
    claims = {c["claim_id"]: c for c in claims_data["claims"]}
    trace: list[dict[str, Any]] = []

    for src in sorted(SRC.rglob("*")):
        if not src.is_file() or src.suffix not in {".tex", ".md"}:
            continue
        rel = src.relative_to(SRC).as_posix()
        target = OUT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        text = src.read_text("utf-8")
        target.write_text(
            resolve(text, values, rel, trace, claims) if src.suffix == ".tex" else text,
            encoding="utf-8",
            newline="\n",
        )
    for name in FIGURES:
        shutil.copy2(PAPER / "figures" / name, OUT / "figures" / name)
    for name in ("llncs.cls", "splncs04.bst"):
        shutil.copy2(TEMPLATE / name, OUT / name)

    # Supplementary material (not compiled; for reviewers and authors).
    sup = OUT / "supplementary"
    shutil.copytree(
        PAPER / "supplementary", sup, ignore=shutil.ignore_patterns("__pycache__")
    )
    shutil.copy2(PAPER / "REPRODUCIBILITY.md", sup / "S9-reproducibility.md")
    lit = sup / "literature-review"
    lit.mkdir()
    for name in (
        "protocol.md",
        "searches.csv",
        "screening.csv",
        "included.csv",
        "extraction.csv",
        "gap-matrix.csv",
    ):
        shutil.copy2(PAPER / "literature-review" / name, lit / name)
    shutil.copytree(
        PAPER / "literature-review" / "update-2026-09-27",
        lit / "update-2026-09-27",
        ignore=shutil.ignore_patterns("raw", "__pycache__", "*.py"),
    )

    tex_files = sorted(OUT.rglob("*.tex"))
    keys = cited_keys(tex_files)
    (OUT / "references.bib").write_text(
        bib_subset(keys), encoding="utf-8", newline="\n"
    )

    # Audit of the \V-bearing source: undefined claims, hand-typed decimals,
    # prohibited claim wording, citations that are not verified matrix rows.
    problems: list[str] = audit_source(claims_data)
    for f in tex_files:
        body = f.read_text("utf-8")
        if "\\V{" in body:
            problems.append(f"unresolved \\V in {f.relative_to(OUT)}")
        for ref in re.findall(
            r"\\(?:input|includegraphics(?:\[[^\]]*\])?)\{([^}]+)\}",
            re.sub(r"(?m)(?<!\\)%.*$", "", body),
        ):
            if not any((OUT / c).is_file() for c in (ref, f"{ref}.tex")):
                problems.append(f"missing asset {ref} (from {f.relative_to(OUT)})")
    for f in OUT.rglob("*"):
        if f.is_file() and f.suffix in {
            ".tex",
            ".bib",
            ".md",
            ".csv",
            ".json",
            ".cls",
            ".bst",
        }:
            body = f.read_text("utf-8", errors="ignore")
            for pat in FORBIDDEN:
                if re.search(pat, body):
                    problems.append(
                        f"filesystem path pattern {pat!r} in {f.relative_to(OUT)}"
                    )
    with (OUT / "CLAIM_TRACE.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(trace[0]))
        w.writeheader()
        w.writerows(trace)

    # Compile a clean copy of the package, then again from an unrelated directory.
    results = {}
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "pkg"
        shutil.copytree(OUT, work, ignore=shutil.ignore_patterns(*REPO_ONLY))
        results["package_compile"] = compile_dir(work)
        if (work / "main.pdf").exists():
            shutil.copy2(work / "main.pdf", OUT / "main.pdf")
    with tempfile.TemporaryDirectory(prefix="overleaf-fresh-") as tmp:
        fresh = Path(tmp) / "unrelated" / "project"
        with zipfile.ZipFile(
            ZIP.with_suffix(".tmp.zip"), "w", zipfile.ZIP_DEFLATED
        ) as z:
            for f in sorted(OUT.rglob("*")):
                if (
                    f.is_file()
                    and f.name not in REPO_ONLY
                    and not f.name.endswith(BUILD_JUNK)
                ):
                    z.write(f, f.relative_to(OUT).as_posix())
        fresh.mkdir(parents=True)
        with zipfile.ZipFile(ZIP.with_suffix(".tmp.zip")) as z:
            z.extractall(fresh)
        results["fresh_directory_compile"] = compile_dir(fresh)
    ZIP.with_suffix(".tmp.zip").replace(ZIP)

    for name, r in results.items():
        if (
            not r["compiled"]
            or r["errors"]
            or r["undefined_refs"]
            or r["undefined_citations"]
            or r["missing_files"]
        ):
            problems.append(f"{name}: {r}")

    with zipfile.ZipFile(ZIP) as z:
        names = z.namelist()
    zip_problems = []
    if "main.tex" not in names:
        zip_problems.append("main.tex not at ZIP root")
    zip_problems += [n for n in names if n.endswith(BUILD_JUNK)]
    problems += zip_problems

    manifest = []
    for f in sorted(OUT.rglob("*")):
        if f.is_file() and f.name != "MANIFEST.json":
            rel = f.relative_to(OUT).as_posix()
            purpose = (
                "manuscript main file"
                if rel == "main.tex"
                else "author metadata"
                if rel == "metadata.tex"
                else "manuscript section"
                if rel.startswith("sections/")
                else "manuscript table"
                if rel.startswith("tables/")
                else "manuscript figure"
                if rel.startswith("figures/")
                else "bibliography"
                if rel == "references.bib"
                else "official Springer template file"
                if rel in ("llncs.cls", "splncs04.bst")
                else "supplementary material"
                if rel.startswith("supplementary/")
                else "compiled PDF (not in ZIP)"
                if rel == "main.pdf"
                else "package documentation"
                if rel.endswith(".md")
                else "provenance / build metadata (not in ZIP)"
            )
            manifest.append(
                dict(
                    file=rel,
                    sha256=sha256(f),
                    size=f.stat().st_size,
                    purpose=purpose,
                    in_zip=rel in names,
                )
            )
    version = dict(
        paper_version="springer-proceedings-draft-1",
        source_commit=git_head(),
        evidence_freeze="satsa-evidence-freeze-v2",
        freeze_json_sha256=sha256(ROOT / "research/evidence/freeze-v2/freeze.json"),
        generation_date=dt.datetime.now(dt.UTC).isoformat(),
        template_source="Springer LaTeX2e Proceedings Template (official ZIP, link.springer.com/series/558)",
        template_version="llncs.cls v2.25 (2026-09-03); splncs04.bst",
        literature_search_date="2026-09-27 (structured search) + 2026-09-27 (update search)",
        environment_reproduction="not demonstrated",
    )
    (OUT / "version.json").write_text(
        json.dumps(version, indent=2) + "\n", encoding="utf-8"
    )
    (OUT / "MANIFEST.json").write_text(
        json.dumps(
            dict(
                schema="satsa-overleaf-manifest/1",
                zip=dict(
                    path="paper/overleaf-springer.zip",
                    sha256=sha256(ZIP),
                    size=ZIP.stat().st_size,
                    files=len(names),
                ),
                files=manifest,
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    report = dict(
        results=results,
        source_claims_used=AUDIT.get("claims_used"),
        claims_resolved=len(trace),
        distinct_claims=len({t["claim_id"] for t in trace}),
        cited=len(keys),
        zip_files=len(names),
        zip_sha256=sha256(ZIP),
        problems=problems,
    )
    print(json.dumps(report, indent=2))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())

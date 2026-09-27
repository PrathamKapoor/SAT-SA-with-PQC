"""Build the submission release candidate, validate it, and write its manifests.

Steps: copy paper/submission into paper/release-candidate (clean files only),
compile the copy in an isolated directory, run the paper audits on paper/ and
paper/submission, write paper/release-candidate/MANIFEST.json and, with
--release-json, the release record (e.g. research/evidence/submission-release.json).
Exits non-zero when any technical check fails. Author inputs are reported, not
filled.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.research.paper_audit import run_audit
from evaluation.research.release import (
    assemble,
    git_state,
    manifest,
    release_record,
    validate,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--submission", type=Path, default=Path("paper/submission"))
    parser.add_argument("--out", type=Path, default=Path("paper/release-candidate"))
    parser.add_argument("--freeze", default="research/evidence/freeze-v2")
    parser.add_argument("--publication", default="research/evidence/publication-v2")
    parser.add_argument("--release-json", type=Path)
    parser.add_argument("--skip-audits", action="store_true")
    args = parser.parse_args(argv)
    repo = Path.cwd()

    assemble(args.submission, Path("paper/VENUE_COMPLIANCE.md"), args.out)
    validation = validate(args.out)
    git = git_state(repo)
    record = manifest(args.out, git)
    (args.out / "MANIFEST.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    audits: dict[str, dict] = {}
    if not args.skip_audits:
        for name, paper in (("paper", Path("paper")), ("submission", args.submission)):
            report = run_audit(Path(args.freeze), paper)
            audits[name] = {
                "ok": report["ok"],
                "claims": report["numerical"]["claims"],
                "claims_used_in_text": report["manuscript"]["used"],
                "citations": report["citations"]["cited"],
                "bib_entries": report["citations"]["bib_entries"],
                "matrix_rows": report["citations"]["matrix_rows"],
                "problems": {
                    k: v["problems"]
                    for k, v in report.items()
                    if isinstance(v, dict) and v.get("problems")
                },
            }
    summary = {
        "release_candidate": str(args.out),
        "files": len(record["files"]),
        "source_commit": record["source_commit"],
        "paper_tree_dirty": record["paper_tree_dirty"],
        "validation": validation,
        "audits": audits,
    }
    if args.release_json:
        release = release_record(
            repo,
            args.out,
            record,
            validation,
            audits,
            venue="IEEE Access",
            article_type="Applied Research",
            freeze=args.freeze,
            publication=args.publication,
        )
        args.release_json.write_text(
            json.dumps(release, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        summary["submission_ready"] = release["submission_ready"]
        summary["author_inputs_open"] = release["author_inputs_open"]
    print(json.dumps(summary, indent=2))
    ok = validation["ok"] and all(a["ok"] for a in audits.values())
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

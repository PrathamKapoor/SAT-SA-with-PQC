"""Apply the screening protocol to candidates.csv and write the screening tables.

Inputs (all in this directory):
  candidates.csv                  deduplicated search results (run_searches.py)
  abstract-stage-decisions.json   single-screener decisions for title-stage passes
  additional-sources.csv          sources not retrieved by the searches
                                  (Phase 12 focused review, snowballing)
Outputs:
  screening.csv   every candidate with stage reached, decision and reason
  included.csv    included sources with classification
  excluded.csv    excluded candidates with reason code

Title-stage exclusions are coded by rule after the manual title decision:
E1 when the record is not a research item (front matter, indexes, peer-review
reports, proceedings volumes), E3 when the title is in the security-operations,
incident or audit-log domain, otherwise E2.
"""

from __future__ import annotations

# ruff: noqa: C408  (keyword dict() calls mirror the CSV columns)
import csv
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent

REASONS = {
    "E1": "not a research item (front matter, index, peer-review report, proceedings volume, advertisement)",
    "E2": "outside scope: not security operations, security/IT process analytics, supervisory analytics or record integrity",
    "E3": "in domain but does not address SAT-SA's positioning questions (assessment, supervision, workflow evidence, prioritisation of entities, human review, record integrity)",
    "E4": "insufficient scholarly content for comparison (practitioner chapter, report or thesis without evaluation)",
    "E5": "duplicate or superseded version of an included or excluded record",
    "E6": "not peer reviewed (preprint server, SSRN, Zenodo, Research Square) and not an authoritative report",
}
_NON_RESEARCH = re.compile(
    r"^(acknowledg|author biography|copyright|dedication|foreword|front-?matter|glossary|index|"
    r"appendix|preface|proceedings \d{4}|peer review|the author$|daily operations|efficient operations)|exam dumps",
    re.IGNORECASE,
)
_IN_DOMAIN = re.compile(
    r"security operation|\bsoc\b|alert|incident|audit|tamper|siem|triage|cyber|suptech|provenance|post-quantum|conformance",
    re.IGNORECASE,
)


def main() -> None:
    cands = list(csv.DictReader((HERE / "candidates.csv").open(encoding="utf-8")))
    decisions = {
        d["key"]: d
        for d in json.loads((HERE / "abstract-stage-decisions.json").read_text("utf-8"))
    }

    def key(r: dict) -> str:
        if r["doi"]:
            return "doi:" + r["doi"].lower()
        return "t:" + re.sub(r"[^a-z0-9]+", " ", r["title"].lower()).strip()

    screening, included, excluded = [], [], []
    for r in cands:
        k = key(r)
        d = decisions.get(k)
        if d:
            row = dict(
                cand_id=r["cand_id"],
                key=k,
                title=r["title"],
                year=r["year"],
                venue=r["venue"],
                doi=r["doi"],
                stage="abstract",
                decision=d["decision"],
                classification=d["classification"],
                reason_code=d["reason_code"],
                note=d["note"],
                hits=r["hits"],
            )
        else:
            code = (
                "E1"
                if _NON_RESEARCH.search(r["title"].strip())
                else ("E3" if _IN_DOMAIN.search(r["title"]) else "E2")
            )
            row = dict(
                cand_id=r["cand_id"],
                key=k,
                title=r["title"],
                year=r["year"],
                venue=r["venue"],
                doi=r["doi"],
                stage="title",
                decision="EXCLUDE",
                classification="",
                reason_code=code,
                note="",
                hits=r["hits"],
            )
        screening.append(row)
        (included if row["decision"] == "INCLUDE" else excluded).append(row)
    missing = set(decisions) - {s["key"] for s in screening}
    if missing:
        raise SystemExit(f"decisions without a candidate: {sorted(missing)}")

    for extra in csv.DictReader(
        (HERE / "additional-sources.csv").open(encoding="utf-8")
    ):
        included.append(
            dict(
                cand_id="",
                key=extra["key"],
                title=extra["title"],
                year=extra["year"],
                venue=extra["venue"],
                doi=extra["doi"],
                stage=extra["origin"],
                decision="INCLUDE",
                classification=extra["classification"],
                reason_code="",
                note=extra["note"],
                hits="",
            )
        )

    fields = list(screening[0])
    for name, rows in (
        ("screening.csv", screening),
        ("included.csv", included),
        ("excluded.csv", excluded),
    ):
        with (HERE / name).open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(
                fh, fieldnames=fields + (["reason"] if name == "excluded.csv" else [])
            )
            w.writeheader()
            for row in rows:
                w.writerow(
                    dict(
                        row,
                        **(
                            {"reason": REASONS[row["reason_code"]]}
                            if name == "excluded.csv"
                            else {}
                        ),
                    )
                )
    by = lambda rows, f: {
        v: sum(1 for r in rows if r[f] == v) for v in sorted({r[f] for r in rows})
    }
    print(
        json.dumps(
            {
                "candidates": len(cands),
                "title_stage_excluded": sum(
                    1 for s in screening if s["stage"] == "title"
                ),
                "abstract_stage": sum(1 for s in screening if s["stage"] == "abstract"),
                "included_from_search": sum(
                    1 for s in screening if s["decision"] == "INCLUDE"
                ),
                "included_additional": len(included)
                - sum(1 for s in screening if s["decision"] == "INCLUDE"),
                "excluded_by_reason": by(excluded, "reason_code"),
                "included_by_class": by(included, "classification"),
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main()

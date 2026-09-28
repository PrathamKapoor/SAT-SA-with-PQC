"""Update search (2026-09-27) for the Springer manuscript: closest prior art and
counterevidence. Runs each query against OpenAlex (title+abstract), keeps the top
15 by relevance, caches raw responses in raw/, and writes queries.csv and
records.csv. Screening decisions are recorded by hand in screening.csv.
"""

from __future__ import annotations

# ruff: noqa: C408  (keyword dict() calls mirror CSV/JSON field names)
import csv
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TOP = 15
QUERIES = [
    (
        "U01",
        "incident management compliance assessment process mining",
        "closest prior art: IM compliance",
    ),
    (
        "U02",
        "ISO 27035 incident management process",
        "closest prior art: ISO 27035 process",
    ),
    (
        "U03",
        "security operations center key performance indicators measurement",
        "counterevidence: SOC KPI measurement",
    ),
    (
        "U04",
        "security operations center audit evidence assessment",
        "counterevidence: evidence-based SOC audit",
    ),
    (
        "U05",
        "conformance checking incident response process",
        "counterevidence: security conformance analytics",
    ),
    (
        "U06",
        "cybersecurity regulator supervision incident reporting data analytics",
        "counterevidence: supervisory analytics",
    ),
    (
        "U07",
        "alert prioritization security operations center evaluation dataset",
        "current alert prioritisation",
    ),
    (
        "U08",
        "tamper-evident audit log digital signature verification decision",
        "decision/record integrity",
    ),
    (
        "U09",
        "peer benchmarking organizations cybersecurity performance comparison",
        "peer benchmarking",
    ),
    (
        "U10",
        "security operations center large language model agent evaluation",
        "current SOC automation landscape",
    ),
]


def _abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    return " ".join(w for _, w in sorted((p, w) for w, ps in inv.items() for p in ps))


def main() -> None:
    raw = HERE / "raw"
    raw.mkdir(exist_ok=True)
    qrows: list[dict[str, Any]] = []
    recs: dict[str, dict[str, Any]] = {}
    for qid, q, purpose in QUERIES:
        path = raw / f"{qid}.json"
        params = {
            "filter": f"title_and_abstract.search:{q},from_publication_date:2015-01-01",
            "per-page": str(TOP),
            "select": "id,doi,display_name,publication_year,type,primary_location,abstract_inverted_index,cited_by_count",
        }
        url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
        if path.exists():
            body = json.loads(path.read_text("utf-8"))
        else:
            req = urllib.request.Request(
                url, headers={"User-Agent": "satsa-literature-update/1.0"}
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                body = json.loads(r.read())
            path.write_text(json.dumps(body), encoding="utf-8")
            time.sleep(2)
        qrows.append(
            dict(
                query_id=qid,
                query=q,
                purpose=purpose,
                source="OpenAlex title_and_abstract.search",
                filters="from 2015-01-01; relevance order; top 15",
                date="2026-09-27",
                result_count=body["meta"]["count"],
                retrieved=len(body["results"]),
            )
        )
        for w in body["results"]:
            doi = (w.get("doi") or "").replace("https://doi.org/", "")
            key = doi.lower() or w["id"]
            src = ((w.get("primary_location") or {}).get("source") or {}).get(
                "display_name"
            ) or ""
            rec = recs.setdefault(
                key,
                dict(
                    key=key,
                    title=w["display_name"],
                    year=w["publication_year"],
                    doi=doi,
                    venue=src,
                    type=w.get("type"),
                    queries=set(),
                    abstract=_abstract(w.get("abstract_inverted_index"))[:900],
                ),
            )
            rec["queries"].add(qid)
    with (HERE / "queries.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(qrows[0]))
        w.writeheader()
        w.writerows(qrows)
    with (HERE / "records.csv").open("w", newline="", encoding="utf-8") as f:
        w2 = csv.writer(f)
        w2.writerow(
            ["rec_id", "title", "year", "doi", "venue", "type", "queries", "abstract"]
        )
        for i, r in enumerate(
            sorted(recs.values(), key=lambda r: (-len(r["queries"]), r["title"] or "")),
            1,
        ):
            w2.writerow(
                [
                    f"U{i:03d}",
                    r["title"],
                    r["year"],
                    r["doi"],
                    r["venue"],
                    r["type"],
                    ";".join(sorted(r["queries"])),
                    r["abstract"],
                ]
            )
    print(f"queries={len(qrows)} unique_records={len(recs)}")


if __name__ == "__main__":
    main()

"""Structured literature search for SAT-SA positioning (Phase 13).

Runs every query in QUERIES against OpenAlex (title+abstract search), Crossref
(bibliographic query) and the arXiv API, stores each raw response under
raw/<source>/<query-id>.json, and writes:

  searches.csv     one row per (query, source): date, filters, result count, retrieved
  candidates.csv   deduplicated retrieved records (DOI, else normalised title)

Raw responses are cached; delete raw/ to re-query. Result counts change over
time, so searches.csv records the date each query ran. This script is not part
of SAT-SA and touches no evidence.
"""

from __future__ import annotations

# ruff: noqa: C408  (keyword dict() calls mirror the CSV columns)
import csv
import datetime as dt
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
FROM_YEAR = 2005
PER_QUERY = 25  # records retrieved per (query, source), by source relevance order
UA = {"User-Agent": "satsa-literature-search/1.0 (structured positioning search)"}

# id, OpenAlex/Crossref free-text query, arXiv query, topic
QUERIES = [
    (
        "Q01",
        '"security operations center" performance measurement',
        'abs:"security operations center" AND abs:performance',
        "SOC performance measurement",
    ),
    (
        "Q02",
        '"security operations center" maturity assessment',
        'abs:"security operations center" AND abs:maturity',
        "SOC maturity / assessment",
    ),
    (
        "Q03",
        '"security operations center" metrics evaluation',
        'abs:"security operations center" AND abs:metrics',
        "SOC metrics",
    ),
    (
        "Q04",
        '"security operations" analytics workflow',
        'abs:"security operations" AND abs:workflow',
        "security operations analytics / workflow",
    ),
    (
        "Q05",
        "security alert prioritization triage",
        "abs:alert AND abs:prioritization AND abs:security",
        "alert prioritization",
    ),
    (
        "Q06",
        '"alert fatigue" security operations',
        'abs:"alert fatigue"',
        "alert fatigue",
    ),
    (
        "Q07",
        '"human-in-the-loop" security operations center',
        'abs:"human-in-the-loop" AND abs:"security operations"',
        "human-in-the-loop SOC",
    ),
    (
        "Q08",
        '"process mining" security incident',
        'abs:"process mining" AND abs:security',
        "security process mining",
    ),
    (
        "Q09",
        '"conformance checking" incident management',
        'abs:"conformance checking" AND abs:incident',
        "conformance checking",
    ),
    (
        "Q10",
        '"missing activities" OR "skipped activities" conformance event log',
        'abs:"conformance checking" AND abs:missing',
        "absence-based process analysis",
    ),
    (
        "Q11",
        '"incident response" process evaluation event log',
        'abs:"incident response" AND abs:"event log"',
        "incident-response workflow analysis",
    ),
    (
        "Q12",
        '"peer group analysis" anomaly detection',
        'abs:"peer group" AND abs:anomaly',
        "peer-group analytics",
    ),
    ("Q13", "suptech supervisory technology", "abs:suptech", "SupTech"),
    (
        "Q14",
        "cybersecurity supervision regulator assessment critical infrastructure",
        "abs:cybersecurity AND abs:supervisory AND abs:assessment",
        "cybersecurity supervision",
    ),
    (
        "Q15",
        '"tamper-evident" log audit',
        'abs:"tamper-evident" AND abs:log',
        "tamper-evident logs",
    ),
    (
        "Q16",
        '"secure audit log" integrity',
        'abs:"audit log" AND abs:integrity',
        "audit integrity",
    ),
    (
        "Q17",
        "cryptographic provenance audit trail decision",
        "abs:provenance AND abs:cryptographic AND abs:audit",
        "cryptographic provenance",
    ),
    (
        "Q18",
        '"post-quantum" signature audit log',
        'abs:"post-quantum" AND abs:"audit log"',
        "PQC audit systems",
    ),
    (
        "Q19",
        '"SOC" analyst decision support evaluation',
        'abs:"SOC analysts" AND abs:"decision support"',
        "SOC decision support",
    ),
    (
        "Q20",
        "IT service management incident event log analysis SLA",
        'abs:"incident management" AND abs:"event log"',
        "ITSM incident logs (external-data context)",
    ),
]


def _get(url: str) -> bytes:
    for attempt in range(5):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=60
            ) as r:
                return r.read()
        except urllib.error.HTTPError as exc:  # rate limits
            if (
                exc.code in (429, 503) and attempt < 4 and "arxiv.org" not in url
            ):  # arXiv throttling (406/429) is recorded, not retried
                time.sleep(10 * (attempt + 1))
                continue
            raise
    raise RuntimeError(url)


def _cached(source: str, qid: str, url: str) -> tuple[bytes, str]:
    path = RAW / source / f"{qid}.json"
    if path.exists():
        rec = json.loads(path.read_text(encoding="utf-8"))
        return rec["body"].encode("utf-8"), rec["retrieved"]
    body = _get(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    today = dt.datetime.now(dt.UTC).date().isoformat()
    path.write_text(
        json.dumps({"url": url, "retrieved": today, "body": body.decode("utf-8")}),
        encoding="utf-8",
    )
    time.sleep(1.5)
    return body, today


def _abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    pos = sorted((p, w) for w, ps in inv.items() for p in ps)
    return " ".join(w for _, w in pos)


def openalex(qid: str, q: str):
    params = {
        "filter": f"title_and_abstract.search:{q},from_publication_date:{FROM_YEAR}-01-01",
        "per-page": str(PER_QUERY),
        "select": "id,doi,display_name,publication_year,type,primary_location,abstract_inverted_index,cited_by_count",
    }
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
    body, day = _cached("openalex", qid, url)
    d = json.loads(body)
    recs = []
    for w in d["results"]:
        src = ((w.get("primary_location") or {}).get("source") or {}).get(
            "display_name"
        ) or ""
        recs.append(
            dict(
                title=w["display_name"] or "",
                year=w.get("publication_year"),
                doi=(w.get("doi") or "").replace("https://doi.org/", ""),
                venue=src,
                type=w.get("type"),
                abstract=_abstract(w.get("abstract_inverted_index"))[:1200],
                url=w["id"],
            )
        )
    filt = f"title_and_abstract.search; from_publication_date {FROM_YEAR}-01-01; relevance order"
    return d["meta"]["count"], recs, day, filt, url


def crossref(qid: str, q: str):
    params = {
        "query.bibliographic": q.replace('"', ""),
        "rows": str(PER_QUERY),
        "filter": f"from-pub-date:{FROM_YEAR}",
        "select": "DOI,title,issued,container-title,type,abstract",
    }
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)
    body, day = _cached("crossref", qid, url)
    m = json.loads(body)["message"]
    recs = []
    for it in m["items"]:
        year = (it.get("issued", {}).get("date-parts") or [[None]])[0][0]
        recs.append(
            dict(
                title=(it.get("title") or [""])[0],
                year=year,
                doi=it.get("DOI", ""),
                venue=(it.get("container-title") or [""])[0],
                type=it.get("type"),
                abstract=re.sub(r"<[^>]+>", "", it.get("abstract", ""))[:1200],
                url="https://doi.org/" + it.get("DOI", ""),
            )
        )
    filt = f"query.bibliographic (quotes removed); from-pub-date {FROM_YEAR}; relevance order"
    return m["total-results"], recs, day, filt, url


def arxiv(qid: str, q: str):
    params = {"search_query": q, "max_results": str(PER_QUERY), "sortBy": "relevance"}
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(
        params, safe=":", quote_via=urllib.parse.quote
    )
    body, day = _cached("arxiv", qid, url)
    ns = {
        "a": "http://www.w3.org/2005/Atom",
        "o": "http://a9.com/-/spec/opensearch/1.1/",
    }
    root = ET.fromstring(body)
    total = int(root.find("o:totalResults", ns).text)
    recs = []
    for e in root.findall("a:entry", ns):
        title = " ".join(e.find("a:title", ns).text.split())
        year = int(e.find("a:published", ns).text[:4])
        recs.append(
            dict(
                title=title,
                year=year,
                doi="",
                venue="arXiv",
                type="preprint",
                abstract=" ".join(e.find("a:summary", ns).text.split())[:1200],
                url=e.find("a:id", ns).text,
            )
        )
    time.sleep(3)
    return (
        total,
        recs,
        day,
        "arXiv abs: field query; relevance order; no date filter",
        url,
    )


def norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def main() -> None:
    searches, cands = [], {}
    for qid, q, aq, topic in QUERIES:
        for source, fn, query in (
            ("OpenAlex", openalex, q),
            ("Crossref", crossref, q),
            ("arXiv", arxiv, aq),
        ):
            try:
                total, recs, day, filt, url = fn(qid, query)
            except Exception as exc:  # noqa: BLE001 - every failed search is recorded in searches.csv
                searches.append(
                    dict(
                        query_id=qid,
                        topic=topic,
                        source=source,
                        query=query,
                        date_searched=dt.datetime.now(dt.UTC).date().isoformat(),
                        filters="",
                        result_count="ERROR: " + str(exc)[:80],
                        retrieved=0,
                        url="",
                    )
                )
                continue
            searches.append(
                dict(
                    query_id=qid,
                    topic=topic,
                    source=source,
                    query=query,
                    date_searched=day,
                    filters=filt,
                    result_count=total,
                    retrieved=len(recs),
                    url=url,
                )
            )
            for r in recs:
                key = (
                    ("doi:" + r["doi"].lower())
                    if r["doi"]
                    else ("t:" + norm_title(r["title"]))
                )
                tkey = "t:" + norm_title(r["title"])
                hit = cands.get(key) or next(
                    (c for c in cands.values() if c["tkey"] == tkey), None
                )
                if hit:
                    hit["hits"].add(f"{qid}/{source}")
                    if not hit["abstract"] and r["abstract"]:
                        hit["abstract"] = r["abstract"]
                    if not hit["doi"] and r["doi"]:
                        hit["doi"] = r["doi"]
                    continue
                cands[key] = dict(r, tkey=tkey, hits={f"{qid}/{source}"})
    with (HERE / "searches.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(searches[0]))
        w.writeheader()
        w.writerows(searches)
    rows = sorted(cands.values(), key=lambda c: (-len(c["hits"]), c["title"].lower()))
    with (HERE / "candidates.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "cand_id",
                "title",
                "year",
                "doi",
                "venue",
                "type",
                "n_hits",
                "hits",
                "url",
                "abstract",
            ]
        )
        for i, c in enumerate(rows, 1):
            w.writerow(
                [
                    f"C{i:04d}",
                    c["title"],
                    c["year"],
                    c["doi"],
                    c["venue"],
                    c["type"],
                    len(c["hits"]),
                    ";".join(sorted(c["hits"])),
                    c["url"],
                    c["abstract"],
                ]
            )
    raw_total = sum(s["retrieved"] for s in searches)
    print(f"searches={len(searches)} retrieved={raw_total} unique={len(rows)}")


if __name__ == "__main__":
    main()

"""Derive SAT-SA assets.csv rows from the destination IPs observed in
converted CIC-IDS2017 alerts (``ingest_adapter.parse_rows`` output).

An asset's criticality is inferred from the highest-severity attack
observed against it — never invented, and always traceable back to
the alerts that produced it. A host that only ever appears in BENIGN
flows never becomes an asset via this module alone; the "silent
critical asset" benchmark scenario deliberately adds such hosts via
``workflow_augmentation`` instead (see that package), since "this
host exists but was never attacked in this window" is not something
``ingest_adapter`` can know from alert data alone.
"""
from __future__ import annotations

from public_benchmarks.provenance import source_derived

SOURCE_DATASET = "CIC-IDS2017"

_SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1,
                  "info": 0, "unknown": 0}


def build_assets(alerts: list) -> list:
    """Return one asset dict per unique destination IP referenced by
    ``alerts`` (the output of ``ingest_adapter.parse_rows``), with
    ``criticality`` set to the highest severity of any alert against
    that host."""
    best: dict = {}
    for a in alerts:
        for asset_id in a["asset_ids"]:
            current = best.get(asset_id)
            if current is None or (
                    _SEVERITY_RANK.get(a["severity"], 0)
                    > _SEVERITY_RANK.get(current, 0)):
                best[asset_id] = a["severity"]
    return [
        {
            "native_id": asset_id,
            "criticality": severity,
            "provenance": source_derived(SOURCE_DATASET).to_dict(),
        }
        for asset_id, severity in sorted(best.items())
    ]


def to_assets_csv(assets: list) -> str:
    import csv
    import io
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["native_id", "criticality"])
    for a in assets:
        writer.writerow([a["native_id"], a["criticality"]])
    return buf.getvalue()

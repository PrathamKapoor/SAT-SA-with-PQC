"""Paper data model: every manuscript number resolved from frozen evidence.

``paper/data/claims-spec.json`` declares each quantitative value used in the
manuscript: its claim id, experiment, canonical bundle, a path into that
bundle's ``raw/results.json`` (or a named derivation computed from the same
file, or a code fact pinned to the freeze's code commit), metric, unit, sample
size, dataset, status, limitations and display format. ``build_paper_data``
verifies every cited bundle against the freeze, resolves every value and
writes ``paper-data.json`` plus ``values.tex`` (LaTeX macros read by the
manuscript through ``\\V{claim-id}``). Nothing is typed by hand.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from evaluation.research.freeze import verify_bundle

PAPER_DATA_SCHEMA = "satsa-paper-data/1"
_CLAIM_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,79}$")


def _walk(value: Any, path: list[Any]) -> Any:
    for step in path:
        if isinstance(step, dict) and "find" in step:
            key, wanted = step["find"]["key"], step["find"]["value"]
            matches = [item for item in value if item.get(key) == wanted]
            if len(matches) != 1:
                raise KeyError(f"find {key}={wanted!r} matched {len(matches)} items")
            value = matches[0]
        else:
            value = value[step]
    return value


# ---------------------------------------------------------------------------
# Named derivations (each reads only the bundle's raw results)
# ---------------------------------------------------------------------------


def _pr01_compare(results: dict[str, Any], args: dict[str, Any]) -> int:
    """Populations where SAT-SA is higher / equal / lower than a baseline."""
    k, metric, baseline, outcome = (
        str(args["k"]),
        args["metric"],
        args["baseline"],
        args["outcome"],
    )
    count = 0
    for replicate in results["metrics"]["replicates"]:
        diff = (
            replicate["methods"]["satsa"][k][metric]
            - replicate["methods"][baseline][k][metric]
        )
        if (
            outcome == "higher"
            and diff > 1e-12
            or outcome == "equal"
            and abs(diff) <= 1e-12
            or outcome == "lower"
            and diff < -1e-12
        ):
            count += 1
    return count


def _pr01_volume_compare(results: dict[str, Any], args: dict[str, Any]) -> int:
    count = 0
    for replicate in results["metrics"]["replicates"]:
        diff = (
            replicate["methods"]["satsa"]["review_volume_to_find_all"]
            - replicate["methods"][args["baseline"]]["review_volume_to_find_all"]
        )
        count += (diff < 0) if args["outcome"] == "fewer" else (diff > 0)
    return count


def _p01_emitted(results: dict[str, Any], args: dict[str, Any]) -> int:
    return sum(
        row["finding_emitted"]
        for row in results["metrics"]["matrix"]
        if row["spread"] == args["spread"]
        and ("size" not in args or row["cohort_size"] == args["size"])
        and ("subject" not in args or row["subject_closure_seconds"] == args["subject"])
    )


def _x03_prevalence(results: dict[str, Any], args: dict[str, Any]) -> float:
    values = [
        g["prevalence"][args["metric"]] for g in results["metrics"]["groups"].values()
    ]
    return {"min": min(values), "max": max(values)}[args["stat"]]


def _x03_saturated(results: dict[str, Any], args: dict[str, Any]) -> int:
    return sum(
        v["flagging_rate"] == 1.0
        for v in results["metrics"]["detector_saturation"].values()
    )


def _x03_zero_dimensions(results: dict[str, Any], args: dict[str, Any]) -> int:
    return sum(
        v["groups_nonzero"] == 0
        for v in results["metrics"]["risk"]["dimensions"].values()
    )


def _r01b_stale_unchanged(results: dict[str, Any], args: dict[str, Any]) -> int:
    count = 0
    for scenario in results["metrics"]["per_scenario"]:
        for row in scenario["conditions"]:
            delta = row.get("paired_delta_vs_control")
            if (
                row["family"] == "staleness"
                and row["validation_status"] == "valid"
                and row.get("validation_warning_count") == 0
                and delta is not None
                and not delta["family_set_changed"]
                and delta["finding_count_change"] == 0
                and not delta["risk_fields_changed"]
            ):
                count += 1
    return count


def _t01_count(results: dict[str, Any], args: dict[str, Any]) -> int:
    return sum(
        m["expected_verification_outcome"] == args["expected"]
        for m in results["mutations"]
    )


def _x02b_relevant_groups(results: dict[str, Any], args: dict[str, Any]) -> int:
    match = re.search(r"(\d+) groups", results["metrics"]["design"]["relevant_set"])
    if match is None:
        raise KeyError("relevant-set size not recorded")
    return int(match.group(1))


def _o02_sum(results: dict[str, Any], args: dict[str, Any]) -> int:
    return sum(v[args["field"]] for v in results["metrics"]["summary"].values())


def _len_path(results: dict[str, Any], args: dict[str, Any]) -> int:
    return len(_walk(results, args["path"]))


DERIVATIONS: dict[str, Callable[[dict[str, Any], dict[str, Any]], Any]] = {
    "len_path": _len_path,
    "o02_sum": _o02_sum,
    "x02b_relevant_groups": _x02b_relevant_groups,
    "pr01_compare": _pr01_compare,
    "pr01_volume_compare": _pr01_volume_compare,
    "p01_emitted": _p01_emitted,
    "x03_prevalence": _x03_prevalence,
    "x03_saturated": _x03_saturated,
    "x03_zero_dimensions": _x03_zero_dimensions,
    "r01b_stale_unchanged": _r01b_stale_unchanged,
    "t01_count": _t01_count,
}


# Code facts as they held in the source the paper describes: the freeze's
# canonical code commit. The product keeps evolving (for example, API routes
# are added), so the paper must not read these from whatever code is
# installed now. Each value was computed with ``_code_fact`` against that
# commit and equals the value in ``paper/data/paper-data.json``. A new code
# fact needs an entry here before the paper can cite it.
PAPER_CODE_FACTS_COMMIT = "837d1eff8f7525a5a8078c524076dfdb52cb79a2"
_ROUTES = "count of @app.<method>( decorators in satsa/api/__init__.py"
_WEIGHT = "satsa.analysis.risk.DIMENSION_WEIGHTS entry"
PAPER_CODE_FACTS: dict[str, dict[str, Any]] = {
    "default_worker_count": {
        "value": 16,
        "derivation": "len(satsa.analysis.run._default_workers(DEFAULT_FAST_CLOSURE_POLICY))",
    },
    "risk_dimension_count": {
        "value": 7,
        "derivation": "len(satsa.analysis.risk.DIMENSION_WEIGHTS)",
    },
    "graph_node_count": {
        "value": 5,
        "derivation": "add_node( calls in AnalysisGraphRuntime.__init__",
    },
    "trust_signature_algorithm": {
        "value": "ML-DSA-65",
        "derivation": "satsa.analysis.trust.DEFAULT_ALGORITHM",
    },
    "api_route_count": {"value": 44, "derivation": _ROUTES},
    "registry_component_count": {
        "value": 32,
        "derivation": "len(satsa.supervisor.agents.AGENT_REGISTRY)",
    },
    "registry_satsa_count": {
        "value": 23,
        "derivation": "len(satsa.supervisor.agents.SATSA_AGENTS)",
    },
    "registry_mlops_count": {
        "value": 9,
        "derivation": "len(satsa.supervisor.agents.RETAINED_MLOPS_AGENTS)",
    },
    "risk_weight:execution_gap": {"value": 25, "derivation": _WEIGHT},
    "risk_weight:peer_deviation": {"value": 20, "derivation": _WEIGHT},
    "risk_weight:detection_gap": {"value": 15, "derivation": _WEIGHT},
    "risk_weight:negative_space": {"value": 15, "derivation": _WEIGHT},
    "risk_weight:anomaly": {"value": 15, "derivation": _WEIGHT},
    "risk_weight:investigation_quality": {"value": 5, "derivation": _WEIGHT},
    "risk_weight:escalation_discipline": {"value": 5, "derivation": _WEIGHT},
}


def paper_code_fact(name: str, freeze_record: dict[str, Any]) -> Any:
    """The pinned value of a code fact for the paper built from this freeze."""
    commit = freeze_record.get("canonical_code_commit")
    if commit != PAPER_CODE_FACTS_COMMIT:
        raise ValueError(
            f"paper code facts are pinned to {PAPER_CODE_FACTS_COMMIT[:7]},"
            f" but the freeze records canonical code commit {str(commit)[:7]}"
        )
    if name not in PAPER_CODE_FACTS:
        raise KeyError(f"code fact {name!r} is not pinned for the paper")
    return PAPER_CODE_FACTS[name]["value"]


def _code_fact(name: str) -> Any:
    """Facts read from the currently installed source (the live product).

    The paper uses ``paper_code_fact``; this reader serves checks of the
    current code and records how each pinned value was derived."""
    if name == "default_worker_count":
        from satsa.analysis.run import DEFAULT_FAST_CLOSURE_POLICY, _default_workers

        return len(_default_workers(DEFAULT_FAST_CLOSURE_POLICY))
    if name == "risk_dimension_count":
        from satsa.analysis.risk import DIMENSION_WEIGHTS

        return len(DIMENSION_WEIGHTS)
    if name == "graph_node_count":
        import inspect

        from satsa.analysis.graph import AnalysisGraphRuntime

        return inspect.getsource(AnalysisGraphRuntime.__init__).count("add_node(")
    if name == "api_route_count":
        import inspect

        from satsa import api

        return len(
            re.findall(r"@app\.(?:get|post|put|patch|delete)\(", inspect.getsource(api))
        )
    if name in ("registry_component_count", "registry_satsa_count", "registry_mlops_count"):
        from satsa.supervisor import agents

        return {
            "registry_component_count": len(agents.AGENT_REGISTRY),
            "registry_satsa_count": len(agents.SATSA_AGENTS),
            "registry_mlops_count": len(agents.RETAINED_MLOPS_AGENTS),
        }[name]
    if name.startswith("risk_weight:"):
        from satsa.analysis.risk import DIMENSION_WEIGHTS

        return DIMENSION_WEIGHTS[name.split(":", 1)[1]]
    if name == "trust_signature_algorithm":
        from satsa.analysis.trust import DEFAULT_ALGORITHM

        return DEFAULT_ALGORITHM
    raise KeyError(f"unknown code fact {name}")


def format_value(value: Any, fmt: str) -> str:
    if value is None:
        return "n/a"
    if fmt == "int":
        return str(int(value))
    if fmt == "pct0":
        return f"{100 * float(value):.0f}\\%"
    if fmt == "pct1":
        return f"{100 * float(value):.1f}\\%"
    if fmt == "str":
        return str(value)
    if fmt == "signed3":
        return f"{float(value):+.3f}"
    if fmt == "signed2":
        return f"{float(value):+.2f}"
    return fmt.format(float(value))


def build_paper_data(freeze_dir: Path, spec_path: Path) -> dict[str, Any]:
    freeze_dir = Path(freeze_dir)
    record = json.loads((freeze_dir / "freeze.json").read_text(encoding="utf-8"))
    bundles = {b["bundle"]: b for b in record["bundles"]}
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    loaded: dict[str, dict[str, Any]] = {}
    claims: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in spec["claims"]:
        claim_id = item["claim_id"]
        if not _CLAIM_ID.fullmatch(claim_id) or claim_id in seen:
            raise ValueError(f"invalid or duplicate claim id {claim_id!r}")
        seen.add(claim_id)
        source: dict[str, Any]
        if "code_fact" in item:
            value = paper_code_fact(item["code_fact"], record)
            source = {"kind": "code", "fact": item["code_fact"]}
        elif "supporting_file" in item:
            import hashlib

            recorded = {
                s["file"]: s["sha256"] for s in record.get("supporting_files", [])
            }
            rel = f"supporting/{item['supporting_file']}"
            path = freeze_dir / rel
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if recorded.get(rel) != digest:
                raise ValueError(
                    f"{claim_id}: supporting file {rel} differs from freeze"
                )
            value = _walk(json.loads(path.read_text(encoding="utf-8")), item["path"])
            source = {
                "kind": "supporting",
                "file": rel,
                "sha256": digest,
                "path": item["path"],
            }
        else:
            name = item["bundle"]
            entry = bundles.get(name)
            if entry is None or entry["role"] not in ("canonical", "supporting"):
                raise ValueError(
                    f"{claim_id}: bundle {name!r} is not canonical in the freeze"
                )
            if name not in loaded:
                path = freeze_dir / "bundles" / name
                problems = verify_bundle(
                    path, expected_manifest_sha256=entry["manifest_sha256"]
                )
                if problems:
                    raise ValueError(f"{name} fails verification: {problems}")
                loaded[name] = json.loads(
                    (path / "raw" / "results.json").read_text(encoding="utf-8")
                )
            results = loaded[name]
            if "derive" in item:
                value = DERIVATIONS[item["derive"]](results, item.get("args", {}))
                source = {
                    "kind": "derived",
                    "bundle": name,
                    "derivation": item["derive"],
                    "args": item.get("args", {}),
                }
            else:
                value = _walk(results, item["path"])
                source = {"kind": "path", "bundle": name, "path": item["path"]}
            source["manifest_sha256"] = entry["manifest_sha256"]
        claims.append(
            {
                "claim_id": claim_id,
                "experiment_id": item["experiment_id"],
                "metric": item["metric"],
                "unit": item.get("unit", ""),
                "sample_size": item.get("sample_size"),
                "dataset": item.get("dataset"),
                "status": item.get("status", "MEASURED"),
                "limitations": item.get("limitations", []),
                "value": value,
                "display": format_value(value, item.get("fmt", "{:.3f}")),
                "source": source,
            }
        )
    return {
        "schema": PAPER_DATA_SCHEMA,
        "freeze_id": record["freeze_id"],
        # location-independent: the freeze directory name, not the local path
        "freeze_dir": freeze_dir.resolve().name,
        "claims": claims,
    }


def values_tex(data: dict[str, Any]) -> str:
    lines = [
        "% Generated from paper/data/paper-data.json; do not edit.",
        f"% Freeze: {data['freeze_id']}",
        "\\makeatletter",
        (
            "\\newcommand{\\V}[1]{\\@ifundefined{pv@#1}{\\PackageError{paperdata}"
            "{Undefined paper value #1}{}}{\\@nameuse{pv@#1}}}"
        ),
    ]
    for claim in data["claims"]:
        # a leading ASCII hyphen would typeset as a hyphen in text mode
        display = re.sub(r"^-(?=\d)", r"\\ensuremath{-}", str(claim["display"]))
        lines.append(f"\\@namedef{{pv@{claim['claim_id']}}}{{{display}}}")
    lines.append("\\makeatother")
    return "\n".join(lines) + "\n"


_MACRO = re.compile(r"\\V\{([^}]+)\}")
_DECIMAL = re.compile(r"(?<![\w\\.{-])\d+\.\d+(?![\w])")


def audit_manuscript(tex_files: list[Path], data: dict[str, Any]) -> dict[str, Any]:
    """Every \\V key must exist; no result-like decimal may be typed by hand."""
    defined = {c["claim_id"] for c in data["claims"]}
    used: set[str] = set()
    undefined: list[str] = []
    typed_decimals: list[str] = []
    for path in tex_files:
        for number, line in enumerate(
            Path(path).read_text(encoding="utf-8").splitlines(), 1
        ):
            # drop comments (an unescaped %) and verbatim text
            stripped = re.split(r"(?<!\\)%", line, maxsplit=1)[0]
            stripped = re.sub(r"\\verb\|[^|]*\|", "", stripped)
            for key in _MACRO.findall(stripped):
                used.add(key)
                if key not in defined:
                    undefined.append(f"{Path(path).name}:{number}:{key}")
            cleaned = _MACRO.sub("", stripped)
            cleaned = re.sub(
                r"\\(cite\w*|ref|label|url|href|includegraphics|input)"
                r"(\[[^\]]*\])?\{[^}]*\}",
                "",
                cleaned,
            )
            for match in _DECIMAL.findall(cleaned):
                typed_decimals.append(f"{Path(path).name}:{number}:{match}")
    return {
        "used": sorted(used),
        "unused": sorted(defined - used),
        "undefined": undefined,
        "typed_decimals": typed_decimals,
    }

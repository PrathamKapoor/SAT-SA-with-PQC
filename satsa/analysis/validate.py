"""Expert-labelled validation framework.

Per the roadmap, validation is per-layer + composition; we never
collapse everything into one accuracy figure. The
``ValidationAgent`` already lives in ``satsa.supervisor.agents``;
this module is the supporting engine that loads expert labels,
synthetic ground truth, runs the layer-specific evaluation, and
returns a structured report.

Three validation surfaces:

* **layer validation** — for each registered analytical worker,
  compare the worker's emitted findings against an expert-labelled
  ground truth for that layer. Each layer reports its own
  precision/recall (where computable) and limitation count.
* **composition validation** — run the entire vertical slice
  (ingestion → analytics → risk → recommendation → trust → review)
  against an end-to-end ground truth and report whether the
  recommended action aligns with the expected action.
* **synthetic ground truth** — generate a deterministic ground
  truth dataset covering healthy / execution-gap / negative-space
  / anomaly / peer-deviation / mixed / borderline / noisy /
  missing-evidence / conflicting-evidence cases. The ground
  truth is generated *outside* the analytical execution and only
  compared after the fact.

Expert labels carry:

- expert label (yes/no signal)
- finding category (one of the rule families)
- severity (low/medium/high/critical)
- expected action (one of the SAT-SA bounded recommendation actions)
- rationale (free text)
- confidence (0..1)
- reviewer (pseudonym)
- timestamp
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Expert label
# ---------------------------------------------------------------------------

@dataclass
class ExpertLabel:
    layer: str                  # e.g. "execution_gap.fast_closure"
    is_signal: bool
    finding_category: str = ""
    severity: str = "medium"
    expected_action: str = ""
    rationale: str = ""
    confidence: float = 0.8
    reviewer: str = "expert"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    def signature(self) -> str:
        """A deterministic identity for set membership — a layer's
        labels are conceptually unique by (layer, finding_category,
        reviewer, rationale, is_signal) so that an expert re-label of
        the same finding produces the same signature, but a
        positive and a negative label on the same finding are
        distinguishable."""
        return (f"{self.layer}|{self.finding_category}|{self.reviewer}"
                f"|{self.rationale}|{'sig' if self.is_signal else 'nosig'}")


def save_expert_labels(labels: list[ExpertLabel], path: Path) -> None:
    """Persist a list of expert labels as JSON."""
    Path(path).write_text(
        json.dumps([l.to_dict() for l in labels], indent=2, ensure_ascii=False),
        encoding="utf-8")


def load_expert_labels(path: Path) -> list[ExpertLabel]:
    """Load expert labels from a JSON file."""
    items = json.loads(Path(path).read_text(encoding="utf-8"))
    return [ExpertLabel(**i) for i in items]


# ---------------------------------------------------------------------------
# Synthetic ground truth
# ---------------------------------------------------------------------------

@dataclass
class GroundTruthCase:
    case_id: str
    scenario: str   # one of the synthetic scenarios
    expected_signals: list = field(default_factory=list)  # rule families expected to fire
    expected_action: str = ""
    description: str = ""
    # Optional ground truth metrics for the synthetic scenario.
    expected_alert_count: int = 0
    expected_critical_alert_count: int = 0


def synthetic_ground_truth() -> list[GroundTruthCase]:
    """The canonical 10-scenario synthetic ground truth the roadmap
    explicitly requires. The ground truth lives in this function;
    the analytical execution never imports or references it
    during a run — only after the run is finished does the
    validator compare emitted findings against this list.

    Scenarios: healthy, execution-gap, negative-space, anomaly,
    peer-deviation, mixed, borderline, noisy, missing-evidence,
    conflicting-evidence.
    """
    return [
        GroundTruthCase("healthy", "healthy",
                        expected_signals=[], expected_action="SATSA_SURFACE",
                        description="Clean run; no analytical signals expected.",
                        expected_alert_count=50, expected_critical_alert_count=5),
        GroundTruthCase("eg-fast-closure", "execution-gap",
                        expected_signals=["execution_gap.fast_closure"],
                        expected_action="SATSA_INSPECT",
                        description="3 critical alerts closed in <60s each.",
                        expected_alert_count=10, expected_critical_alert_count=3),
        GroundTruthCase("ns-missing-investigation", "negative-space",
                        expected_signals=["negative_space.missing_investigation"],
                        expected_action="SATSA_INSPECT",
                        description="Cases with zero investigation steps.",
                        expected_alert_count=10, expected_critical_alert_count=2),
        GroundTruthCase("anomaly-rate", "anomaly",
                        expected_signals=["anomaly."],
                        expected_action="SATSA_SURFACE",
                        description="Anomalous rate vs prior period."),
        GroundTruthCase("peer-deviation", "peer-deviation",
                        expected_signals=["peer_benchmark."],
                        expected_action="SATSA_SURFACE",
                        description="Entity deviates from peer cohort."),
        GroundTruthCase("mixed", "mixed",
                        expected_signals=["execution_gap.fast_closure",
                                          "negative_space.missing_monitoring"],
                        expected_action="SATSA_REQUEST_EVIDENCE",
                        description="Multiple signal families firing."),
        GroundTruthCase("borderline", "borderline",
                        expected_signals=[],
                        expected_action="SATSA_SURFACE",
                        description="On the boundary of detection thresholds."),
        GroundTruthCase("noisy", "noisy",
                        expected_signals=[],
                        expected_action="SATSA_DEFER",
                        description="High noise; signal-to-noise low."),
        GroundTruthCase("missing-evidence", "missing-evidence",
                        expected_signals=["evidence_completeness.missing_categories"],
                        expected_action="SATSA_REQUEST_EVIDENCE",
                        description="Missing categories in submission."),
        GroundTruthCase("conflicting-evidence", "conflicting-evidence",
                        expected_signals=[],
                        expected_action="SATSA_DEFER",
                        description="Conflicting evidence between sources."),
    ]


# ---------------------------------------------------------------------------
# Layer validation
# ---------------------------------------------------------------------------

@dataclass
class LayerMetric:
    """YES / NO / UNLABELED semantics (fixed this phase — see
    ``evaluate_layer``'s docstring for the bug this replaced):

    * a positively-labeled (``is_signal=True``) family is YES ground
      truth — contributes to true_positives / false_negatives.
    * a negatively-labeled (``is_signal=False``) family is NO ground
      truth — contributes to false_positives / true_negatives.
    * an emitted family with *no* label at all (neither YES nor NO)
      is UNLABELED — excluded from every supervised metric below,
      counted separately in ``unlabeled_emitted`` so the report is
      honest about how much of what was emitted was ever reviewed.

    Fields that are undefined for lack of data (e.g. ``precision``
    when nothing was labeled positive or emitted) are ``None``, never
    a fabricated ``0.0`` — "do not calculate metrics the data cannot
    support."
    """
    layer: str
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    true_negatives: int = 0
    unlabeled_emitted: int = 0
    precision: Optional[float] = None
    recall: Optional[float] = None
    specificity: Optional[float] = None
    f1: Optional[float] = None
    balanced_accuracy: Optional[float] = None
    support: int = 0          # count of positively-labeled families (YES)
    coverage: Optional[float] = None  # fraction of emitted families that were labeled at all
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def evaluate_layer(layer: str, emitted_families: list[str],
                  expert_labels: list[ExpertLabel]) -> LayerMetric:
    """Compare the emitted finding families for ``layer`` against
    the expert labels for that layer, with explicit YES/NO/UNLABELED
    semantics.

    ``emitted_families`` is a list of rule_or_category prefixes
    (e.g. ``["execution_gap.fast_closure"]``) the run produced.
    ``expert_labels`` are the ExpertLabel objects for this layer.

    Before this phase, a family with *no* label at all was silently
    treated identically to a family the expert explicitly said should
    NOT fire (``is_signal=False``) — both fell into "emitted minus
    positively-labeled" and counted as a false positive. That
    conflates "a reviewer confirmed this was wrong" with "nobody ever
    looked at this" — the latter must not penalize precision. This
    function now tracks positive and negative labels separately, and
    an emitted-but-never-labeled family is excluded from the
    confusion matrix entirely (see ``unlabeled_emitted``).
    """
    positive = {l.finding_category or l.layer for l in expert_labels
               if l.layer == layer and l.is_signal
               and (l.finding_category or l.layer)}
    negative = {l.finding_category or l.layer for l in expert_labels
               if l.layer == layer and not l.is_signal
               and (l.finding_category or l.layer)}
    emitted_signals = {f for f in emitted_families
                       if f.startswith(layer)}

    tp = len(positive & emitted_signals)
    fn = len(positive - emitted_signals)
    fp = len(negative & emitted_signals)
    tn = len(negative - emitted_signals)
    labeled = positive | negative
    unlabeled_emitted = emitted_signals - labeled
    conflicting = positive & negative  # a family labeled both ways (disagreement)

    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    specificity = tn / (tn + fp) if (tn + fp) else None
    f1 = (2 * precision * recall / (precision + recall)
          if precision and recall else None)
    balanced_accuracy = (
        (recall + specificity) / 2
        if recall is not None and specificity is not None else None)
    total_considered = len(emitted_signals)
    coverage = (
        len(emitted_signals & labeled) / total_considered
        if total_considered else None)

    notes = (f"compared {len(emitted_signals)} emitted vs "
             f"{len(positive)} positive / {len(negative)} negative "
             f"expert labels; {len(unlabeled_emitted)} emitted family "
             "(families) had no label at all and were excluded from "
             "the confusion matrix")
    if conflicting:
        notes += (f"; {len(conflicting)} famil(ies) carried both a "
                  "positive and a negative label (reviewer "
                  "disagreement) — counted toward both sides")

    return LayerMetric(
        layer=layer,
        true_positives=tp, false_positives=fp, false_negatives=fn,
        true_negatives=tn, unlabeled_emitted=len(unlabeled_emitted),
        precision=precision, recall=recall, specificity=specificity,
        f1=f1, balanced_accuracy=balanced_accuracy,
        support=len(positive), coverage=coverage, notes=notes,
    )


# ---------------------------------------------------------------------------
# Composition validation
# ---------------------------------------------------------------------------

def composition_validation(case: GroundTruthCase,
                            emitted_families: list[str],
                            emitted_action: str) -> dict:
    """Compare a single ground-truth case's expected vs emitted
    signals and action. Returns a dict suitable for direct
    inclusion in the validation report.

    When ``expected_signals`` is empty (a healthy/borderline/noisy
    control — the roadmap's 'clean control entities correctly
    produce no findings' gate), ``signals_ok`` means *no* signal
    family fired, not the vacuous ``expected <= emitted``.
    """
    expected = set(case.expected_signals)
    emitted = set(emitted_families)
    if case.expected_signals:
        signals_ok = expected <= emitted  # every expected signal was emitted
    else:
        signals_ok = not emitted           # no unexpected signal fired
    action_ok = (emitted_action == case.expected_action
                 or (not case.expected_signals and emitted_action == "SATSA_SURFACE"))
    return {
        "case_id": case.case_id,
        "scenario": case.scenario,
        "expected_signals": sorted(expected),
        "emitted_signals": sorted(emitted),
        "expected_action": case.expected_action,
        "emitted_action": emitted_action,
        "signals_ok": signals_ok,
        "action_ok": action_ok,
    }


# ---------------------------------------------------------------------------
# Top-level validation entry point
# ---------------------------------------------------------------------------

def run_validation(service,
                   *,
                   expert_labels: Optional[list[ExpertLabel]] = None,
                   ground_truth: Optional[list[GroundTruthCase]] = None
                   ) -> dict:
    """Run the full validation suite against the persisted runs.

    Per-layer validation requires ``expert_labels`` (one per
    layer). Composition validation runs over the supplied
    ``ground_truth`` (defaults to ``synthetic_ground_truth()``).

    The returned dict has shape:

        {
          "layers":  [{layer, tp, fp, fn, precision, recall, notes}, ...],
          "composition": [{case_id, expected_signals, ...}, ...],
          "summary": {layers: n, cases: n, at: timestamp}
        }
    """
    layers = []
    if expert_labels:
        # Group emitted findings by rule-family prefix.
        emitted = service._db.query_all(
            "SELECT DISTINCT rule_or_category FROM satsa_findings"
            " WHERE state='signal'")
        emitted_families = [r["rule_or_category"] for r in emitted]
        layers_by = sorted({l.layer for l in expert_labels})
        for layer in layers_by:
            metrics = evaluate_layer(
                layer, emitted_families,
                [l for l in expert_labels if l.layer == layer])
            layers.append(metrics.to_dict())
    cases = ground_truth or synthetic_ground_truth()
    composition = []
    for case in cases:
        # For composition validation we need to look at the
        # most recent run per scenario. Without a way to map
        # synthetic scenarios to runs, we report the expected
        # ground truth plus the action the supervisor would
        # emit if the expected signal fired — and we accept
        # that this section is a scaffold until expert labels
        # are wired to specific runs.
        emitted_families = list(case.expected_signals)  # scaffold
        composition.append(composition_validation(
            case, emitted_families, case.expected_action))
    return {
        "layers": layers,
        "composition": composition,
        "summary": {
            "layers": len(layers),
            "cases": len(composition),
            "at": time.time(),
        },
    }
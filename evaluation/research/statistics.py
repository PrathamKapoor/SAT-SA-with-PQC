"""Descriptive and paired-comparison statistics for research experiments.

Standard library only. Every summary carries its sample size, unit of
analysis and an adequacy label so that small samples are reported as
exploratory rather than dressed up as confirmatory results. No p-values
are produced: the current experiments are not pre-registered hypothesis
tests, and repeated timing trials on one machine are not independent
replications of a population.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from statistics import fmean, median
from typing import Any

from evaluation.workload.experiment import _percentile

# Below this many observations a p95 is not reported: with fewer than 20
# values the 95th percentile is an interpolation between the top two points.
MIN_N_FOR_P95 = 20
# Below this many paired observations a bootstrap interval is too unstable
# to report; the comparison is labelled exploratory instead.
MIN_N_FOR_BOOTSTRAP = 10
DEFAULT_CONFIDENCE = 0.95
DEFAULT_RESAMPLES = 10_000


def adequacy(n: int) -> str:
    """Classify how far a sample of ``n`` independent units can be pushed."""
    if n < MIN_N_FOR_BOOTSTRAP:
        return "exploratory: too few observations for an interval estimate"
    return "descriptive with bootstrap interval; not a hypothesis test"


def describe(values: Sequence[float], *, unit: str) -> dict[str, Any]:
    """Median/p95/mean/range of repeated measurements of one quantity."""
    data = sorted(float(v) for v in values)
    n = len(data)
    if n == 0:
        return {
            "n": 0,
            "unit": unit,
            "median": None,
            "p95": None,
            "mean": None,
            "min": None,
            "max": None,
            "p95_note": "no observations",
        }
    enough = n >= MIN_N_FOR_P95
    return {
        "n": n,
        "unit": unit,
        "median": round(median(data), 6),
        "p95": round(_percentile(data, 0.95), 6) if enough else None,
        "p95_note": None if enough else f"not reported for n < {MIN_N_FOR_P95}",
        "mean": round(fmean(data), 6),
        "min": round(data[0], 6),
        "max": round(data[-1], 6),
    }


def bootstrap_interval(
    values: Sequence[float],
    statistic: Callable[[Sequence[float]], float] = median,
    *,
    confidence: float = DEFAULT_CONFIDENCE,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = 0,
) -> dict[str, Any] | None:
    """Seeded percentile bootstrap interval, or None when n is too small."""
    data = [float(v) for v in values]
    if len(data) < MIN_N_FOR_BOOTSTRAP:
        return None
    if not 0 < confidence < 1 or resamples < 100:
        raise ValueError("confidence must be in (0, 1) and resamples >= 100")
    rng = random.Random(seed)
    estimates = sorted(
        statistic([rng.choice(data) for _ in data]) for _ in range(resamples)
    )
    tail = (1 - confidence) / 2
    return {
        "method": "percentile bootstrap",
        "confidence": confidence,
        "resamples": resamples,
        "seed": seed,
        "lower": round(_percentile(estimates, tail), 6),
        "upper": round(_percentile(estimates, 1 - tail), 6),
    }


def paired_comparison(
    baseline: Sequence[float],
    treatment: Sequence[float],
    *,
    unit: str,
    pairing: str,
    seed: int = 0,
) -> dict[str, Any]:
    """Summarize treatment − baseline over matched pairs.

    Reports the median paired difference (absolute effect), the relative
    difference against the baseline median when that is non-zero, and a
    seeded bootstrap interval for the median difference when n allows.
    """
    if len(baseline) != len(treatment):
        raise ValueError("paired comparison requires equal-length samples")
    differences = [float(t) - float(b) for b, t in zip(baseline, treatment)]
    n = len(differences)
    base_median = median(baseline) if n else None
    diff_median = median(differences) if n else None
    relative = (
        round(diff_median / base_median, 6)
        if diff_median is not None and base_median not in (None, 0)
        else None
    )
    return {
        "n_pairs": n,
        "unit": unit,
        "pairing": pairing,
        "baseline": describe(baseline, unit=unit),
        "treatment": describe(treatment, unit=unit),
        "median_difference": round(diff_median, 6) if diff_median is not None else None,
        "relative_median_difference": relative,
        "relative_note": None
        if relative is not None
        else "undefined: baseline median is zero or absent",
        "treatment_greater_in_pairs": sum(d > 0 for d in differences),
        "median_difference_interval": bootstrap_interval(differences, seed=seed),
        "adequacy": adequacy(n),
        "inference": "none: no p-value or significance claim is made",
    }

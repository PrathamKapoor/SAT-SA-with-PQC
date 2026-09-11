"""Literature-named baseline outlier/anomaly detectors, plus two
deliberately naive controls, for comparing against SAT-SA's own
analytical workers on the same data.

None of this is SAT-SA's detection logic — every function here is a
standard, off-the-shelf statistical method (z-score, MAD, IQR) or an
intentionally naive control (a fixed threshold with no distributional
awareness; pure random flagging) so a reviewer can see SAT-SA's actual
lift over both "a domain expert's naive fixed rule" and "chance," not
a number with nothing to compare it to. This module is deliberately
free of any import from ``satsa.*`` — a baseline that could reach into
SAT-SA's own code would not be an independent comparison.
"""
from __future__ import annotations

import random
import statistics


def zscore_baseline(values: list, *, k: float = 2.0) -> list:
    """Flag values more than ``k`` standard deviations from the mean.
    Fewer than 2 values (stdev undefined) or zero variance flags
    nothing — never divides by zero, never fabricates a flag."""
    if len(values) < 2:
        return [False] * len(values)
    mean = statistics.fmean(values)
    stdev = statistics.pstdev(values)
    if stdev == 0:
        return [False] * len(values)
    return [abs(v - mean) / stdev > k for v in values]


def mad_baseline(values: list, *, k: float = 3.5) -> list:
    """Median Absolute Deviation baseline — robust to the outliers
    themselves (unlike z-score, which uses the mean/stdev the
    outliers distort). Uses the standard 0.6745 consistency constant
    so the modified z-score is comparable in scale to a normal
    z-score (Iglewicz & Hoaglin, the commonly cited MAD threshold)."""
    if len(values) < 2:
        return [False] * len(values)
    med = statistics.median(values)
    mad = statistics.median(abs(v - med) for v in values)
    if mad == 0:
        return [False] * len(values)
    return [abs(0.6745 * (v - med) / mad) > k for v in values]


def iqr_baseline(values: list, *, k: float = 1.5) -> list:
    """Tukey's IQR fence: flag values outside
    ``[Q1 - k*IQR, Q3 + k*IQR]``. Needs at least 4 points to form two
    non-empty halves; fewer flags nothing."""
    if len(values) < 4:
        return [False] * len(values)
    sorted_v = sorted(values)
    mid = len(sorted_v) // 2
    lower_half = sorted_v[:mid]
    upper_half = sorted_v[mid:] if len(sorted_v) % 2 == 0 else sorted_v[mid + 1:]
    q1 = statistics.median(lower_half)
    q3 = statistics.median(upper_half)
    iqr = q3 - q1
    if iqr == 0:
        return [False] * len(values)
    lo, hi = q1 - k * iqr, q3 + k * iqr
    return [v < lo or v > hi for v in values]


def fixed_threshold_baseline(values: list, *, threshold: float,
                             below: bool = True) -> list:
    """A single fixed operational constant with zero distributional
    awareness — the naive rule a domain expert might hand-write
    ("anything closed under 10 minutes looks suspicious")."""
    return [(v < threshold) if below else (v > threshold) for v in values]


def random_baseline(n: int, *, fraction: float, seed: int) -> list:
    """Flags a random ``fraction`` of ``n`` items — the chance-
    agreement control. Deterministic given the same ``seed``, so
    results are reproducible. Any detector that cannot beat this on
    the same data adds no value over guessing."""
    if not (0.0 <= fraction <= 1.0):
        raise ValueError("fraction must be in [0, 1]")
    if n < 0:
        raise ValueError("n must be >= 0")
    rng = random.Random(seed)
    k = round(n * fraction)
    idx = set(rng.sample(range(n), k)) if n else set()
    return [i in idx for i in range(n)]


def severity_only_baseline(severities: list, *,
                           flag_severities=("critical",)) -> list:
    """Flags purely by declared severity, ignoring any temporal or
    statistical signal — the simplest possible triage rule, and the
    natural baseline for comparing against SAT-SA's prioritization
    (not just its anomaly detectors)."""
    flagset = set(flag_severities)
    return [s in flagset for s in severities]


def score(flags: list, labels: list) -> dict:
    """Precision/recall/F1 of a boolean flag list against boolean
    ground-truth labels of the same length. Mirrors
    ``satsa.analysis.validate.evaluate_layer``'s convention: an
    undefined ratio (e.g. no positive labels at all) is ``None``,
    never a fabricated ``0.0``."""
    if len(flags) != len(labels):
        raise ValueError("flags and labels must be the same length")
    tp = sum(1 for f, l in zip(flags, labels) if f and l)
    fp = sum(1 for f, l in zip(flags, labels) if f and not l)
    fn = sum(1 for f, l in zip(flags, labels) if not f and l)
    tn = sum(1 for f, l in zip(flags, labels) if not f and not l)
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * precision * recall / (precision + recall)
          if precision and recall else None)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": precision, "recall": recall, "f1": f1}

"""Head-to-head comparison: run every statistical baseline plus a real
SAT-SA worker's own flags against the same data, scored against the
SAME ground truth. The ground truth is stated by construction (which
records are deliberately anomalous, which are not) — the same
"generator defines truth before detection" discipline documented in
``satsa.analysis.synth``, not inferred from SAT-SA's own output (that
would let SAT-SA grade itself).
"""
from __future__ import annotations

from evaluation.baselines.statistical import (
    fixed_threshold_baseline,
    iqr_baseline,
    mad_baseline,
    random_baseline,
    score,
    zscore_baseline,
)


def compare_closure_time_detectors(
    close_times: list, labels: list, *,
    satsa_flags: list,
    fixed_threshold_seconds: float = 600.0,
    seed: int = 42,
) -> dict:
    """Compare z-score / MAD / IQR / fixed-threshold / random against
    ``satsa_flags`` (the caller's own SAT-SA worker output for the
    same records), all scored against the same ``labels``.

    ``labels`` must be independently defined ground truth — e.g. which
    alerts were deliberately constructed as fast-closures — never
    derived from any detector's own output.
    """
    n = len(close_times)
    if len(labels) != n or len(satsa_flags) != n:
        raise ValueError(
            "close_times, labels, and satsa_flags must be the same length")
    random_fraction = (sum(1 for l in labels if l) / n) if n else 0.0
    return {
        "zscore": score(zscore_baseline(close_times), labels),
        "mad": score(mad_baseline(close_times), labels),
        "iqr": score(iqr_baseline(close_times), labels),
        "fixed_threshold": score(
            fixed_threshold_baseline(close_times, threshold=fixed_threshold_seconds),
            labels),
        "random": score(
            random_baseline(n, fraction=random_fraction, seed=seed), labels),
        "satsa_fast_closure": score(satsa_flags, labels),
    }

"""Literature-named baseline detectors + scoring, kept independent of
``satsa.analysis`` so a baseline can never accidentally import or call
SAT-SA's own detection logic. See ``evaluation.baselines.statistical``
for the detectors and ``evaluation.baselines.compare`` for the
head-to-head comparison against a SAT-SA worker on the same data.
"""
from __future__ import annotations

from evaluation.baselines.statistical import (
    fixed_threshold_baseline,
    iqr_baseline,
    mad_baseline,
    random_baseline,
    score,
    severity_only_baseline,
    zscore_baseline,
)

__all__ = [
    "fixed_threshold_baseline", "iqr_baseline", "mad_baseline",
    "random_baseline", "score", "severity_only_baseline", "zscore_baseline",
]

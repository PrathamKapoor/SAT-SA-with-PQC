"""SAT-SA evaluation harness — separate from ``satsa/`` by design.

Holds evaluation code whose ground truth must stay independent of the
detectors being evaluated: the workload/prioritization-lift experiment
(``evaluation.workload``) today, with baselines/ablations/statistics
to follow as later phases build them out (see docs/roadmap-status.md
P21-P23). Nothing in ``satsa/`` imports from here; this package
imports *from* ``satsa`` to drive real runs, never the reverse.
"""

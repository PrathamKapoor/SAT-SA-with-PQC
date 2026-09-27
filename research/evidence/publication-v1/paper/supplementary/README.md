# Supplementary material

Supplementary sections for the SAT-SA manuscript. Files under `generated/`
are rebuilt from `research/evidence/freeze-v2` by
`python scripts/build_paper_assets.py` and checked byte for byte by
`python scripts/audit_paper.py`; do not edit them.

| Section | File | Content |
| --- | --- | --- |
| S1 | `generated/S1-configurations.md`, `generated/experiments.json` | full configuration, seed, code commit, dataset descriptor, environment and manifest hash of every canonical experiment |
| S2 | `S2-metric-definitions.md` | metric and statistic definitions |
| S3 | `generated/S3-robustness.md` | imperfect-evidence results by family and omission rate (R01b) |
| S4 | `generated/S4-mutation-matrix.md` | TRUST-SAT mutation matrix with failure categories (T01) |
| S5 | `generated/S5-peer-sweep.md` | all 96 peer-sweep cells (P01) |
| S6 | `generated/S6-statistical-audit.md` | statistical audit of every reported estimate; dataset characteristics |
| S7 | `S7-dataset-mapping.md` | UCI-498 to SAT-SA field mapping and semantic assumptions |
| S8 | `S8-limitations.md` | research limitations and threats to validity |
| S9 | `../REPRODUCIBILITY.md` | reproduction commands, seeds, levels, what cannot be reproduced |
| S10 | `generated/S10-additional-results.md` | remaining result tables (controlled, prioritization, ablation, orchestration, recovery, external, deployment smoke) |

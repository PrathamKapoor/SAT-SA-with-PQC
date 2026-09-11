# Expert labels — status and honest scope

`expert-labels.sample.json` in this directory is an **illustrative
template**, not a record of real security-examiner review. Every
entry is tagged `"reviewer": "sample-template"` so this is never
mistaken for production validation data. It exists to prove the
layer-validation wiring (`satsa/analysis/validate.py`,
`sat-sa validate --expert-labels <path>`) computes real
precision/recall against findings an actual run emits — see
`tests/test_phase62_satsa_expert_validation.py`.

Each entry corresponds to a finding family the committed demo
dataset (`sat-sa demo`) is already known to emit, so the sample
file produces non-trivial (not 0/0, not vacuous 1.0/1.0) metrics
out of the box.

## What this closes

Before this fix, `sat-sa validate` never passed `expert_labels`
into `run_validation()`, so the `layers` section of every report
was unconditionally empty — the precision/recall machinery had no
test coverage against real labels at all. `--expert-labels` is now
wired end to end: CLI → `load_expert_labels()` →
`run_validation(svc, expert_labels=...)` → real per-layer TP/FP/FN.

## What this does NOT close

Real production expert-label volume — labels from actual NCIIPC/SOC
examiners reviewing actual findings — is still pending. That
requires human domain review and cannot be honestly fabricated by
an engineering session. Use this template as the input schema and
wiring proof; replace its contents with real reviewer output before
treating layer-validation metrics as production evidence.

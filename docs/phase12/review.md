# Phase 12 — Human Review Workflow

## Goal

Make supervisory judgement a first-class concept in SAT-SA: an
authenticated examiner's confirm / dismiss / escalate / annotate /
request_review action on a finding, with a complete audit trail.

## What is recorded

Every `record_review` call writes one row to
`satsa_review_decisions`:

| Column | Purpose |
|---|---|
| `id` | The decision's own opaque id |
| `finding_id` | The finding acted on |
| `principal_identity_id` | Who acted (the platform identity layer decides *how* this id is established; the audit row records it faithfully) |
| `action` | One of `confirm` / `dismiss` / `escalate` / `annotate` / `request_review` |
| `reason` | Free-text justification, required by the audit trail |
| `occurred_at` | When |
| `previous_revision_id` | For a correction, the decision it supersedes; append-only chain |
| `finding_content_digest` | The *live* content digest of the finding at the moment the decision was made (so the audit row is bound to a specific version of the record) |
| `content_digest` | The decision's own content digest (SHA3-256 of its canonical dict) |

The decision is **append-only** by convention. A correction is a
new row with `previous_revision_id` pointing to the prior
decision, never an in-place edit.

## What the decision does *not* do

* It does not change the underlying finding's `state`. The
  reviewer's verdict is recorded *about* the finding, not
  applied to it. A "dismiss" leaves the finding visible to the
  audit trail; it does not vanish from the run.
* It does not invent an enterprise authentication system. The
  `principal_identity_id` is whatever the platform's identity
  layer hands in. The audit row records it faithfully — it does
  not verify the caller.
* It does not call the trust layer itself. A future
  `verify_run` may detect a tampered finding, and the decision
  row's captured `finding_content_digest` will then no longer
  match the live digest, so an auditor can see the decision was
  made on a different version of the record.

## How to use

```python
from satsa.service import SatsaService
from satsa.analysis.run import RunService

service = SatsaService(database)

# 1. run the analytics
result = service.run_analysis(entity_id, assessment_id)
fid = result.finding_ids[0]

# 2. capture the finding's current digest
from satsa.analysis.run import RunService as _RS
finding_row = database.query_one(
    "SELECT * FROM satsa_findings WHERE id=?", (fid,))
digest = _RS._live_digest_for_finding(finding_row)

# 3. record the review
entry = service.record_review(
    finding_id=fid, principal_identity_id="identity-007",
    action="escalate", reason="needs second-pair-of-eyes",
    finding_content_digest=digest,
)

# 4. query the audit trail for a finding
history = service.review_history(fid)   # chronological, append-only
```

## Tests

`tests/test_phase12_satsa_review.py` — 8 tests:

* domain validation: every action in `REVIEW_ACTIONS` is accepted;
  an unknown action is rejected with `ValueError`;
* persistence: a recorded decision is queryable, all fields
  round-trip;
* the captured `finding_content_digest` is the live digest of
  the finding at decision time;
* the append-only chain: a correction references the previous
  decision via `previous_revision_id`;
* chronological history query;
* integrity: tampering the finding after a decision makes the
  decision's captured digest no longer match the live one.

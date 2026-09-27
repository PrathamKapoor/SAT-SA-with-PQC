# Response to reviewers (template)

Manuscript: *Record-Level Supervisory Analytics for Security Operations Centres*
(IEEE Access). Submission ID: [ID]. Decision date: [date].

This template has no content yet: no reviews have been received. Fill in one
block per reviewer comment and quote each comment verbatim.

Rules for responses:

- **Numbers.** Every changed or new number must come from
  `research/evidence/freeze-v2` or from a new, separately identified experiment
  (new experiment ID, source commit, manifest, bundle, hash, and a new freeze).
  Never type a number into the text; add a claim to `paper/data/claims-spec.json`
  and use `\V{}`.
- **Frozen evidence.** Do not edit freeze-v1, freeze-v2 or the publication-v1
  and publication-v2 snapshots.
- **Unfixable requests.** If a request exceeds the evidence (for example real SOC
  data or a user study), say so and add the gap to the limitations. Do not
  manufacture evidence.
- **Before resubmitting.** Run `python scripts/audit_paper.py` and
  `python scripts/audit_paper.py --paper paper/submission`, and make a new
  publication snapshot.

---

## Reviewer [n]

### Comment [n.m]

> [verbatim reviewer comment]

**Response.** [Agree / partly agree / respectfully disagree, with the reason.]

**Evidence.** [Experiment ID, bundle, claim ID(s) or literature source; or "no
new evidence; wording change only"; or "evidence not available: gap stated".]

**Change made.** [Exact change, or "none" with justification.]

**Location.** [Section / table / figure / page and line in the revised PDF.]

---

## Summary of changes

| # | Reviewer / comment | Change | Location | New evidence? |
| --- | --- | --- | --- | --- |
| 1 | | | | |

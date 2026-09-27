# Human Review Study Protocol — evidence-only vs SAT-SA-assisted review

**Status: PROTOCOL READY — NOT EXECUTED.** No participant has been
recruited, no session has run, and no human-study result exists. Nothing
in this repository reports review time, agreement, completeness or
decision quality from people. Do not cite this document as evidence of
any effect.

## Question

Does presenting a submission through SAT-SA (findings, cited evidence,
risk, recommendation) change how accurately, completely and quickly a
reviewer reaches a supervisory judgement, compared with reviewing the
same submission's raw evidence alone?

This is a within-subject comparison of two presentation conditions. It
is not a comparison between SAT-SA and NCIIPC examiners, and reviewers
recruited for it are "independent cyber-security reviewers" in the
sense of `public_benchmarks/review_packet.py`, not regulators.

## Participants

- **Role:** SOC analysts, security faculty or experienced students who
  can read alert/case/investigation records. Record role using the
  existing `REVIEWER_ROLES` vocabulary; record years of SOC experience.
- **Exclusions:** anyone who authored SAT-SA detectors, fixtures or the
  case set; anyone who has seen the case set before.
- **Target size:** decide before recruitment. With a paired design,
  12 reviewers × 8 cases gives 96 paired observations but only 12
  independent units; report it as exploratory unless a pre-registered
  power analysis on a pilot supports more.
- **Consent/ethics:** written informed consent, right to withdraw,
  pseudonymous participant ids, no personal data in result files.
  Obtain institutional approval where the institution requires it
  before any session.

## Case set

- Draw cases from the controlled catalog fixtures
  (`satsa.analysis.compval.SCENARIO_MAP`) and, where available, from the
  robustness conditions (`evaluation/research/robustness.py`) so that
  each case has a declared ground-truth issue set that is independent
  of SAT-SA output.
- Include at least one healthy (no-issue) case and one case whose
  evidence is incomplete, so "no concern" and "insufficient evidence"
  are legitimate answers.
- Freeze the case set, its ground truth and its digest before the first
  session; record the digest in the study manifest.

## Conditions and randomization

- **Evidence-only:** reviewer sees the submitted CSV records (alerts,
  cases, steps, escalations, dispositions, assets) in a neutral table
  view.
- **SAT-SA-assisted:** reviewer sees the same records plus the SAT-SA
  explanation built by `public_benchmarks.review_packet.build_review_packet`
  (the same `assemble_explanation` output the product shows).
- Each reviewer sees every case once, half under each condition. Assign
  condition per case with a seeded counterbalanced Latin square so that
  each case appears equally often under each condition across reviewers.
- Randomize case order per reviewer with a recorded seed
  (`seed_base + participant_index`).

## Task and completion criteria

For each case the reviewer answers the five fixed `QUESTIONS` in
`public_benchmarks/review_packet.py` and additionally lists the
supervisory issues they believe are present. A case is complete when
every question has an answer and the reviewer submits. Time limit per
case: 15 minutes; a timeout is recorded as incomplete, not as wrong.

## Measures

| Measure | Definition | Unit |
| --- | --- | --- |
| Review time | Submit time − case open time | seconds, per case |
| Evidence retrieval time | Time to first cite a specific supporting record | seconds, per case |
| Issue recall | Declared ground-truth issues the reviewer identified / declared issues | per case |
| Issue precision | Correct identified issues / all identified issues | per case |
| Decision agreement | Reviewer action vs case's declared expected action | match per case |
| Completeness | Answered questions / 5 | per case |

Ground truth comes only from the frozen case set, never from SAT-SA
output.

## Analysis plan (fix before data collection)

- Independent unit: reviewer. Pairing: condition within reviewer.
- Primary outcome: issue recall. Secondary: review time, agreement,
  completeness.
- Report per-condition medians, the median paired difference and a
  seeded percentile bootstrap interval using
  `evaluation/research/statistics.paired_comparison`, resampling
  reviewers (not cases).
- Multiple secondary outcomes: report all of them; apply Holm correction
  if any p-value is reported.
- Label the study exploratory unless the pre-declared sample size is met.

## Data handling

Store raw responses as JSON per session (participant pseudonym, case
id, condition, timestamps, answers). Write results with
`evaluation.research.artifacts.write_experiment_bundle` using
`data_origin: "controlled"` and a dataset descriptor naming the frozen
case set digest. Never mix these results with synthetic experiment
outputs.

## Eligibility screen (ask before consent)

1. Have you reviewed security alerts, incident tickets or SOC cases as part of
   work, teaching or supervised training? (must be yes)
2. Years of that experience: <1, 1–3, 3–5, >5 (recorded, not a criterion).
3. Did you contribute to SAT-SA code, fixtures or this case set? (must be no)
4. Have you seen any of the study cases before? (must be no)

## Participant instructions (read verbatim)

"You will review 8 short cases from a fictional organisation's security
operations records. For each case, decide whether it needs supervisory
follow-up, how severe it is, what evidence is missing, and what action you
recommend. In some cases you will also see an automated analysis; it may be
wrong, and you should use your own judgement. There is no penalty for saying
evidence is insufficient. Work at your normal pace; each case closes after 15
minutes. Your answers are recorded under a code, not your name."

## Condition ordering

With 8 cases (C1…C8) and two conditions (E = evidence-only, A = assisted),
participants are assigned in blocks of four to these sequences, and case order
within each sequence is shuffled with `seed = 20261001 + participant_index`:

| Block position | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | E | A | E | A | E | A | E | A |
| 2 | A | E | A | E | A | E | A | E |
| 3 | E | E | A | A | E | E | A | A |
| 4 | A | A | E | E | A | A | E | E |

## Data collection record (one JSON object per case response)

```json
{"schema": "satsa-review-response/1", "participant_id": "p-012",
 "case_id": "C3", "condition": "A", "sequence_position": 5,
 "opened_at": "2026-10-01T10:02:11Z", "first_evidence_cited_at": "...",
 "submitted_at": "...", "timed_out": false,
 "answers": {"worthy_of_review": true, "severity": "high",
             "missing_evidence": "...", "next_action": "...",
             "priority_ranking_acceptable": null},
 "issues_identified": ["execution_gap.fast_closure"]}
```

`priority_ranking_acceptable` is null in the evidence-only condition.
Participant ids are pseudonyms; the key linking them to consent forms is kept
offline by the study lead and never enters the repository.

## Procedure

1. Freeze the case set and ground truth; record their SHA-256 in the study
   manifest; obtain approval where required.
2. Pilot with 2 participants whose data are excluded; fix only instructions or
   tooling, never the analysis plan.
3. Run sessions; record every response, including timeouts and withdrawals.
4. Analyse exactly as planned above; report every outcome, including null and
   negative results.

## Current state

- Implemented and tested: review packet construction and agreement
  scoring (`public_benchmarks/review_packet.py`), expert-label import
  and layer validation (`sat-sa validate --expert-labels`,
  `docs/demo/EXPERT_LABELS.md`), paired statistics and bundle writer.
- Not implemented: a session runner/timer UI for participants. Building
  one would be a frontend change and is outside the current backend
  scope.
- Not executed: recruitment, sessions, analysis. **No results exist.**

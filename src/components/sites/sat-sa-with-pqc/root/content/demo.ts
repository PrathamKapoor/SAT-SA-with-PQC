/**
 * Real data captured from a live run of the committed demo (scripts/serve_ui.py), 2026-09-12 —
 * used to drive the actual charts and the interactive finding walkthrough. Nothing here is
 * synthesized for the page; every value matches a screenshot in
 * docs/design-references/satsa-with-pqc/.
 */

export type RiskBand = "low" | "medium";

export interface EntityRisk {
  rank: number;
  entity: string;
  score: number;
  band: RiskBand;
  topContributor: string;
}

/** From the live /entities roster, ranked by current supervisory risk. */
export const entityRiskContent: EntityRisk[] = [
  { rank: 1, entity: "CSE-ANOM", score: 42, band: "medium", topContributor: "execution_gap.ack_without_investigation" },
  { rank: 2, entity: "CSE-EXEC", score: 40, band: "medium", topContributor: "execution_gap.fast_closure" },
  { rank: 3, entity: "CSE-NEG", score: 40, band: "medium", topContributor: "execution_gap.ack_without_investigation" },
  { rank: 4, entity: "CSE-PEER", score: 29, band: "medium", topContributor: "execution_gap.ack_without_investigation" },
  { rank: 5, entity: "ACME-BANK", score: 26, band: "low", topContributor: "execution_gap.ack_without_investigation" },
  { rank: 6, entity: "ACME-BANK-WEB", score: 26, band: "low", topContributor: "execution_gap.ack_without_investigation" },
  { rank: 7, entity: "CSE-HEALTHY", score: 19, band: "low", topContributor: "no findings in execution_gap (weight 25)" },
];

/** From the live /entities/{ACME-BANK} risk decomposition — only dimensions with findings shown;
 * the other 5 of the 7 dimensions carry no findings for this entity and score 0. */
export const acmeBankRiskContent = {
  entity: "ACME-BANK",
  score: 26,
  scoreMax: 100,
  confidence: "low",
  findings: 8,
  assessments: 1,
  dimensions: [
    { dimension: "execution_gap", score: 17.4, max: 25, findingCount: 3 },
    { dimension: "anomaly", score: 8.2, max: 15, findingCount: 2 },
  ],
};

/** From the live finding detail page for finding_fefd75d2b61943d8b5ec1ec60abb7a63 — copied verbatim. */
export const findingWalkthroughContent = {
  entity: "ACME-BANK",
  rule: "execution_gap.ack_without_investigation",
  title: "Execution Gap: Ack Without Investigation",
  state: "signal" as const,
  confidence: 90,
  evidenceCount: 4,
  reviewCount: 0,
  trust: "ML-DSA-65",
  rationale:
    "4 acknowledged-and-closed alert(s) had fewer than 2 investigation step(s) recorded across their linked case(s). Closure followed acknowledgement, but with no traceable investigation behind it.",
  why: {
    intro: "The analytical rule that fired, the thresholds it compared against, and the observed value.",
    rows: [
      { field: "Observed statistic", value: "4.0000" },
      { field: "Effect (deviation)", value: "1.0000" },
      { field: "Threshold", value: "2.0000" },
      { field: "Confidence · analytical_support", value: "0.900" },
      { field: "Confidence · evidence_completeness", value: "1.000" },
      { field: "Confidence · overall", value: "0.900" },
      { field: "Confidence · peer_confidence", value: "—" },
    ],
  },
  evidence: {
    intro: "Source-record pointers that the finding was built from — 4 rows from one CSV submission.",
    rows: [
      { record: "srcrec_21b748c…", submission: "submission_908fd…", format: "csv", locator: "row 1" },
      { record: "srcrec_2852dd6…", submission: "submission_908fd…", format: "csv", locator: "row 2" },
      { record: "srcrec_ce57224…", submission: "submission_908fd…", format: "csv", locator: "row 3" },
      { record: "srcrec_34ac3b3…", submission: "submission_908fd…", format: "csv", locator: "row 4" },
    ],
  },
  recommendation: {
    action: "INSPECT INVESTIGATION",
    detail:
      "The alert was acknowledged but the linked case has no recorded investigation. Inspect the case for any out-of-band work, or confirm the absence is a process gap.",
    caveat: "Recommendation is a hint, not a decision. The examiner remains responsible for the final supervisory determination.",
  },
  reviewHistory: "No human review recorded yet.",
  limitation:
    "Heuristic on raw step count. ‘Meaningful’ investigation is not a count, and shallow-but-substantive cases may be mis-flagged. See the rule rationale and individual case drill-down for context.",
};

export const agentCompositionContent = {
  mlops: 9,
  satsa: 23,
  total: 32,
};

export const coverageContent = {
  value: 92.5,
  statements: 5372,
  missed: 405,
  scope: "satsa/ + evaluation/",
};

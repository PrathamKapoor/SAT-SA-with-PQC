/**
 * SAT-SA NCIIPC Supervisory Workbench: Governance, Audit & PQC Ledger
 * Verifiable trust indicators, lineage graphs, and statutory defense records.
 */

export interface AuditLedgerEntry {
  id: string;
  blockHeight: number;
  occurredAt: string;
  principalIdentity: string;
  role: string;
  action: "SUBMISSION_INGEST" | "ANALYSIS_RUN" | "DISPOSITION_RECORD" | "DISPOSITION_REVERSAL" | "POLICY_OVERRIDE" | "AUDIT_EXPORT";
  subjectType: "entity" | "finding" | "submission" | "assessment";
  subjectIdentifier: string;
  previousBlockDigestSha3: string;
  currentBlockDigestSha3: string;
  pqcSignatureAlgorithm: "ML-DSA-65";
  pqcSignatureVerified: boolean;
  notes: string;
}

export const governanceConfig = {
  engineVersion: "0.16.0-phase52-ui",
  qsmlopsVersion: "0.1.0",
  rulesetVersion: "rules-nciipc-2026.08-rev4",
  thresholdCalibrationVersion: "calib-finsec-2026.08.1",
  cryptographicStandard: "NIST FIPS 204 (ML-DSA-65) + FIPS 202 (SHA3-256)",
  hashChainedBlocksTotal: 103,
  ledgerIntegrityStatus: "intact_verified" as const,
  tamperCount: 0,
  airGapCompliance: "100% verified (0 outbound socket calls, 0 CDN links, 0 remote font requests)",
  statutoryRetentionPolicy: "NCIIPC Cyber Rule 7: 7-Year Immutable Supervisory Audit Trail",
  lastFullLedgerAuditTimestamp: "2026-09-12T04:10:00Z",
};

export const auditLedgerEntries: AuditLedgerEntry[] = [
  {
    id: "blk-103",
    blockHeight: 103,
    occurredAt: "2026-09-06T15:30:00Z",
    principalIdentity: "EXAM-SHARMA-01",
    role: "Lead NCIIPC Supervisory Examiner",
    action: "DISPOSITION_RECORD",
    subjectType: "finding",
    subjectIdentifier: "queue-007 (CSE-EXEC PRIV-ELEV-12)",
    previousBlockDigestSha3: "9b4e7201c89012a45612...",
    currentBlockDigestSha3: "33ea8192b0c410948ea1...",
    pqcSignatureAlgorithm: "ML-DSA-65",
    pqcSignatureVerified: true,
    notes: "Disposition set to NOT_SUBSTANTIATED. Physical optical commissioning logs verified.",
  },
  {
    id: "blk-102",
    blockHeight: 102,
    occurredAt: "2026-09-05T11:20:00Z",
    principalIdentity: "EXAM-RAO-04",
    role: "Senior Supervisory Analyst",
    action: "DISPOSITION_RECORD",
    subjectType: "finding",
    subjectIdentifier: "queue-004 (CSE-Z BGP-HIJACK-AL-41)",
    previousBlockDigestSha3: "8821bc09a41920847c10...",
    currentBlockDigestSha3: "9b4e7201c89012a45612...",
    pqcSignatureAlgorithm: "ML-DSA-65",
    pqcSignatureVerified: true,
    notes: "Disposition set to NEEDS_MORE_INFO. Formal request for upstream carrier NOC logs issued.",
  },
  {
    id: "blk-101",
    blockHeight: 101,
    occurredAt: "2026-09-01T02:15:30Z",
    principalIdentity: "SYSTEM_SUPERVISOR_RUNNER",
    role: "Automated Analysis Orchestrator",
    action: "ANALYSIS_RUN",
    subjectType: "assessment",
    subjectIdentifier: "CYCLE-2026-08-RUN-12",
    previousBlockDigestSha3: "771920acb0918234ea99...",
    currentBlockDigestSha3: "8821bc09a41920847c10...",
    pqcSignatureAlgorithm: "ML-DSA-65",
    pqcSignatureVerified: true,
    notes: "Deterministic analysis run completed across 42 CSEs. 85 signals synthesized into 8 attention entities.",
  },
  {
    id: "blk-100",
    blockHeight: 100,
    occurredAt: "2026-08-31T23:59:12Z",
    principalIdentity: "INGEST_DAEMON_AIRGAP",
    role: "Provenance Ingestion Collector",
    action: "SUBMISSION_INGEST",
    subjectType: "submission",
    subjectIdentifier: "SUB-2026-08-CSEX-001",
    previousBlockDigestSha3: "6612940bc0192847ea11...",
    currentBlockDigestSha3: "771920acb0918234ea99...",
    pqcSignatureAlgorithm: "ML-DSA-65",
    pqcSignatureVerified: true,
    notes: "Verified ML-DSA-65 signature on CSE-X submission payload. 1,428,912 records ingested.",
  },
];

/**
 * SAT-SA NCIIPC Supervisory Workbench: Data Submissions & Input Integrity
 * Distinguishes true operational absence from dataset ingestion failures.
 */

export interface SubmissionRecord {
  id: string;
  submissionIdentifier: string;
  entitySlug: string;
  entityName: string;
  reportingPeriod: string;
  format: "CSV Multi-file" | "JSON Lines" | "SQLite DB" | "Encrypted Tarball";
  sourceOrigin: string;
  ingestTimestamp: string;
  schemaValidationStatus: "passed" | "warning" | "failed";
  schemaValidationErrors: string[];
  missingMandatoryFields: string[];
  referentialIntegrityFailuresCount: number;
  duplicateOrConflictingRecordsCount: number;
  assetInventoryFreshnessDays: number;
  assetInventoryStatus: "fresh" | "acceptable" | "stale";
  contentHashSha3: string;
  pqcSignatureAlgorithm: string;
  pqcSignatureVerified: boolean;
  recordsTotal: number;
  recordsAccepted: number;
  recordsQuarantined: number;
  recordsRejected: number;
  negativeSpaceReliabilityScore: number; // 0 - 100%
  validationReportDownloadUrl: string;
}

export const submissions: SubmissionRecord[] = [
  {
    id: "sub-001",
    submissionIdentifier: "SUB-2026-08-CSEX-001",
    entitySlug: "cse-x",
    entityName: "CSE-X (National Payments Gateway)",
    reportingPeriod: "August 2026",
    format: "CSV Multi-file",
    sourceOrigin: "FinSec Airgap Diode Transfer #49",
    ingestTimestamp: "2026-08-31T23:59:12Z",
    schemaValidationStatus: "passed",
    schemaValidationErrors: [],
    missingMandatoryFields: [],
    referentialIntegrityFailuresCount: 14,
    duplicateOrConflictingRecordsCount: 2,
    assetInventoryFreshnessDays: 16,
    assetInventoryStatus: "fresh",
    contentHashSha3: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    pqcSignatureAlgorithm: "ML-DSA-65 (NIST FIPS 204)",
    pqcSignatureVerified: true,
    recordsTotal: 1428928,
    recordsAccepted: 1428912,
    recordsQuarantined: 14,
    recordsRejected: 2,
    negativeSpaceReliabilityScore: 94.8,
    validationReportDownloadUrl: "/api/reports/validation/SUB-2026-08-CSEX-001.json",
  },
  {
    id: "sub-002",
    submissionIdentifier: "SUB-2026-08-CSEY-001",
    entitySlug: "cse-y",
    entityName: "CSE-Y (State Grid Dispatch Center)",
    reportingPeriod: "August 2026",
    format: "SQLite DB",
    sourceOrigin: "SCADA Secure Storage Replicator",
    ingestTimestamp: "2026-09-01T18:30:00Z",
    schemaValidationStatus: "passed",
    schemaValidationErrors: [],
    missingMandatoryFields: [],
    referentialIntegrityFailuresCount: 4,
    duplicateOrConflictingRecordsCount: 0,
    assetInventoryFreshnessDays: 28,
    assetInventoryStatus: "fresh",
    contentHashSha3: "91d54f76269b002bc56df69616e1e85ab8f5d5b78e227d8db198c642646d6d87",
    pqcSignatureAlgorithm: "ML-DSA-65 (NIST FIPS 204)",
    pqcSignatureVerified: true,
    recordsTotal: 840210,
    recordsAccepted: 840206,
    recordsQuarantined: 4,
    recordsRejected: 0,
    negativeSpaceReliabilityScore: 98.2,
    validationReportDownloadUrl: "/api/reports/validation/SUB-2026-08-CSEY-001.json",
  },
  {
    id: "sub-003",
    submissionIdentifier: "SUB-2026-08-CSEN-001",
    entitySlug: "cse-neg",
    entityName: "CSE-NEG (Naval Dockyard Systems)",
    reportingPeriod: "August 2026",
    format: "JSON Lines",
    sourceOrigin: "Naval Intranet Encrypted Optical Disc",
    ingestTimestamp: "2026-08-28T14:10:00Z",
    schemaValidationStatus: "warning",
    schemaValidationErrors: [
      "Field 'source_packet_hash' contains 320 empty string records",
      "Syslog stream truncated at day 12 of 60",
    ],
    missingMandatoryFields: ["packet_checksum_sha256"],
    referentialIntegrityFailuresCount: 142,
    duplicateOrConflictingRecordsCount: 38,
    assetInventoryFreshnessDays: 114,
    assetInventoryStatus: "stale",
    contentHashSha3: "a712f00994cb1947e112d8a01129b008819230dca...",
    pqcSignatureAlgorithm: "ML-DSA-65 (NIST FIPS 204)",
    pqcSignatureVerified: true,
    recordsTotal: 340100,
    recordsAccepted: 339580,
    recordsQuarantined: 482,
    recordsRejected: 38,
    negativeSpaceReliabilityScore: 61.4, // Low reliability -> marks negative space findings with explicit data gap warning!
    validationReportDownloadUrl: "/api/reports/validation/SUB-2026-08-CSEN-001.json",
  },
  {
    id: "sub-004",
    submissionIdentifier: "SUB-2026-08-CSEZ-001",
    entitySlug: "cse-z",
    entityName: "CSE-Z (National Satellite Telemetry Hub)",
    reportingPeriod: "August 2026",
    format: "Encrypted Tarball",
    sourceOrigin: "Space Ground Station Hardened Link",
    ingestTimestamp: "2026-09-04T09:15:00Z",
    schemaValidationStatus: "passed",
    schemaValidationErrors: [],
    missingMandatoryFields: [],
    referentialIntegrityFailuresCount: 8,
    duplicateOrConflictingRecordsCount: 1,
    assetInventoryFreshnessDays: 22,
    assetInventoryStatus: "fresh",
    contentHashSha3: "5f8a002194bb1082ce771092aa...",
    pqcSignatureAlgorithm: "ML-DSA-65 (NIST FIPS 204)",
    pqcSignatureVerified: true,
    recordsTotal: 2190450,
    recordsAccepted: 2190441,
    recordsQuarantined: 8,
    recordsRejected: 1,
    negativeSpaceReliabilityScore: 97.6,
    validationReportDownloadUrl: "/api/reports/validation/SUB-2026-08-CSEZ-001.json",
  },
];

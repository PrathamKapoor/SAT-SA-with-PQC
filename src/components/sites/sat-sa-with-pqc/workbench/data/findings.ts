/**
 * SAT-SA NCIIPC Supervisory Workbench — Authoritative Findings Repository
 * Structured evidence narratives, peer context, detector lineage, and raw rows.
 */

export interface SupportingEvidenceRecord {
  id: string;
  alertId: string;
  timestampCreated: string;
  timestampAck: string;
  timestampClosed: string;
  durationSeconds: number;
  assetId: string;
  assetCriticality: "Tier-1 Critical" | "High" | "Medium";
  linkedCaseId: string | null;
  escalationRecordId: string | null;
  actorId: string;
  rawJsonSnippet: string;
}

export interface Finding {
  id: string;
  findingSlug: string;
  title: string;
  entitySlug: string;
  entityName: string;
  period: string;
  severity: "critical" | "high" | "medium" | "low";
  confidence: "high" | "medium" | "low";
  findingFamily: "execution_gap" | "negative_space" | "anomaly" | "peer_deviation";
  findingFamilyLabel: string;
  ruleOrCategory: string;

  // Narrative components
  observedPattern: string;
  whyThisMatters: string;
  peerContext: {
    cohortName: string;
    cohortMedianPct: number;
    entityObservedPct: number;
    varianceRatio: number;
    description: string;
  };
  systemLimitation: string;

  // Technical & Provenance metadata
  submissionId: string;
  contentHashSha3: string;
  ingestionTimestamp: string;
  policyControlExpectation: string;
  detectorVersion: string;
  rulesThresholds: string;
  calibrationVersion: string;

  // Facts vs Inference vs Recommendation
  observedFacts: string[];
  systemInferences: string[];
  recommendedAction: string;

  // Timeline
  reconstructedTimeline: {
    timestamp: string;
    step: string;
    detail: string;
    actorOrSystem: string;
  }[];

  // Supporting evidence rows
  evidenceRecords: SupportingEvidenceRecord[];
}

export const findings: Finding[] = [
  {
    id: "fnd-csex-001",
    findingSlug: "critical-alerts-closed-without-escalation",
    title: "Critical alerts closed without escalation record",
    entitySlug: "cse-x",
    entityName: "CSE-X (National Payments Gateway)",
    period: "August–September 2026",
    severity: "critical",
    confidence: "high",
    findingFamily: "execution_gap",
    findingFamilyLabel: "Execution Gap",
    ruleOrCategory: "execution_gap.escalation_bypass",

    observedPattern: "18 critical alerts on Tier-1 core banking payment switchgear were closed within 4 minutes without an escalation record or formal incident case link.",
    whyThisMatters: "National Critical Information Infrastructure Protection Centre (NCIIPC) Sec 4.2.1 and entity internal SOC Operating Manual specify that all P1/Critical alerts on designated Tier-1 switchgear mandate formal case registration within 15 minutes. Rapid closures without tickets indicate potential triage bypass or metric gaming.",
    
    peerContext: {
      cohortName: "Large financial-services CSEs",
      cohortMedianPct: 2.1,
      entityObservedPct: 31.0,
      varianceRatio: 14.8,
      description: "Across the cohort of 14 large financial CSEs, the median rate of critical alerts closed without formal escalation is 2.1%. In CSE-X, 31.0% of critical alerts were closed without escalation, representing a 14.8× statistical outlier.",
    },

    systemLimitation: "This finding cannot prove that an out-of-band or verbal escalation did not occur. It demonstrates an absence of verifiable operational evidence within the periodic SIEM and ticketing dataset submitted by the CSE.",

    submissionId: "SUB-2026-08-CSEX-001",
    contentHashSha3: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    ingestionTimestamp: "2026-08-31T23:59:12Z",
    policyControlExpectation: "NCIIPC Cybersecurity Control Spec (FinSec-2024), Control OP-4: Mandatory multi-tier escalation for switchboard anomalies.",
    detectorVersion: "satsa-worker-execgap:v1.4.2",
    rulesThresholds: "threshold_closure_sec <= 300, require_case=true, asset_tier=1",
    calibrationVersion: "calib-2026.08.1-fin",

    observedFacts: [
      "Alert A-1001 created at 10:00:12 UTC, acknowledged at 10:02:04 UTC, and closed at 10:04:18 UTC (elapsed time: 246 seconds).",
      "Field 'linked_case_id' is NULL across all 18 flagged alerts.",
      "Field 'escalation_record_id' is NULL across all 18 flagged alerts.",
      "Target asset 'CORE-SWIFT-01' is registered as Tier-1 Critical in the national asset ledger.",
      "Identical pattern verified across 17 additional distinct records between 2026-08-12 and 2026-08-28.",
    ],

    systemInferences: [
      "The rapid triage duration (<4 minutes) is statistically inconsistent with meaningful forensic inspection of transaction memory dumps.",
      "Absence of ticketing links indicates a structural procedural breakdown or automated macro-closure without analyst oversight.",
      "Correlation with shift handover logs indicates 14 of the 18 occurrences coincided with the 10:00 UTC morning shift transition.",
    ],

    recommendedAction: "Issue formal supervisory inquiry requesting full shift logs, terminal screen captures, and manual logbooks for analyst operator OP-881 for the period 2026-08-12 through 2026-08-28.",

    reconstructedTimeline: [
      { timestamp: "2026-08-14 10:00:12", step: "Alert Inception", detail: "CORE-SWIFT-01 triggered signature SIGN-8821: Unauthorized Memory Write attempt on transaction daemon.", actorOrSystem: "SIEM Sensor 04" },
      { timestamp: "2026-08-14 10:02:04", step: "Triage Acknowledged", detail: "Alert state updated to 'IN_PROGRESS' by triage operator OP-881.", actorOrSystem: "Operator OP-881" },
      { timestamp: "2026-08-14 10:04:18", step: "Premature Closure", detail: "Alert marked 'CLOSED_FALSE_POSITIVE'. Note: 'Routine memory sync'. No ticket generated.", actorOrSystem: "Operator OP-881" },
      { timestamp: "2026-08-31 23:59:12", step: "Submission Ingestion", detail: "CSE-X periodic audit bundle SUB-2026-08-CSEX-001 ingested and validated.", actorOrSystem: "SAT-SA Ingest Engine" },
      { timestamp: "2026-09-01 02:14:08", step: "Worker Execution", detail: "Worker ExecutionGapWorker evaluated rule execution_gap.escalation_bypass with confidence 0.94.", actorOrSystem: "SAT-SA Analysis Engine" },
    ],

    evidenceRecords: [
      {
        id: "ev-001",
        alertId: "A-1001",
        timestampCreated: "2026-08-14T10:00:12Z",
        timestampAck: "2026-08-14T10:02:04Z",
        timestampClosed: "2026-08-14T10:04:18Z",
        durationSeconds: 246,
        assetId: "CORE-SWIFT-01",
        assetCriticality: "Tier-1 Critical",
        linkedCaseId: null,
        escalationRecordId: null,
        actorId: "OP-881",
        rawJsonSnippet: '{"alert_id":"A-1001","src_ip":"192.168.10.42","dest_asset":"CORE-SWIFT-01","sig":"MEM_WRITE_UNAUTH","status":"CLOSED","case_ref":null,"escalated":false,"closure_reason":"Routine memory sync"}',
      },
      {
        id: "ev-002",
        alertId: "A-1002",
        timestampCreated: "2026-08-15T10:01:05Z",
        timestampAck: "2026-08-15T10:02:50Z",
        timestampClosed: "2026-08-15T10:04:40Z",
        durationSeconds: 215,
        assetId: "CORE-SWIFT-01",
        assetCriticality: "Tier-1 Critical",
        linkedCaseId: null,
        escalationRecordId: null,
        actorId: "OP-881",
        rawJsonSnippet: '{"alert_id":"A-1002","src_ip":"192.168.10.42","dest_asset":"CORE-SWIFT-01","sig":"MEM_WRITE_UNAUTH","status":"CLOSED","case_ref":null,"escalated":false,"closure_reason":"Routine memory sync"}',
      },
      {
        id: "ev-003",
        alertId: "A-1003",
        timestampCreated: "2026-08-18T10:00:44Z",
        timestampAck: "2026-08-18T10:01:55Z",
        timestampClosed: "2026-08-18T10:03:59Z",
        durationSeconds: 195,
        assetId: "SWITCH-PRD-01",
        assetCriticality: "Tier-1 Critical",
        linkedCaseId: null,
        escalationRecordId: null,
        actorId: "OP-881",
        rawJsonSnippet: '{"alert_id":"A-1003","src_ip":"10.0.4.19","dest_asset":"SWITCH-PRD-01","sig":"BGP_FLAP_ERR","status":"CLOSED","case_ref":null,"escalated":false,"closure_reason":"Routine maintenance"}',
      },
      {
        id: "ev-004",
        alertId: "A-1004",
        timestampCreated: "2026-08-20T10:02:11Z",
        timestampAck: "2026-08-20T10:03:10Z",
        timestampClosed: "2026-08-20T10:05:01Z",
        durationSeconds: 170,
        assetId: "SWITCH-PRD-02",
        assetCriticality: "Tier-1 Critical",
        linkedCaseId: null,
        escalationRecordId: null,
        actorId: "OP-882",
        rawJsonSnippet: '{"alert_id":"A-1004","src_ip":"10.0.4.20","dest_asset":"SWITCH-PRD-02","sig":"BGP_FLAP_ERR","status":"CLOSED","case_ref":null,"escalated":false,"closure_reason":"Transient peering flap"}',
      },
    ],
  },
  {
    id: "fnd-csex-002",
    findingSlug: "critical-asset-telemetry-absent",
    title: "Critical-asset telemetry absent (Negative-space gap)",
    entitySlug: "cse-x",
    entityName: "CSE-X (National Payments Gateway)",
    period: "August–September 2026",
    severity: "critical",
    confidence: "high",
    findingFamily: "negative_space",
    findingFamilyLabel: "Negative Space",
    ruleOrCategory: "negative_space.telemetry_blackout",

    observedPattern: "7 designated Tier-1 switchgear and database assets in the active inventory had zero telemetry, audit, or access logs submitted across the 60-day assessment window.",
    whyThisMatters: "Negative-space gaps represent unmonitored attack paths. If critical transactional hardware does not produce audit logs, compromise cannot be detected or investigated.",
    
    peerContext: {
      cohortName: "Large financial-services CSEs",
      cohortMedianPct: 0.0,
      entityObservedPct: 8.4,
      varianceRatio: 8.4,
      description: "Across the cohort, 0.0% of Tier-1 assets have telemetry voids. CSE-X has 7 out of 83 registered Tier-1 assets missing from telemetry streams.",
    },

    systemLimitation: "The negative-space detector confirms that submitted archives contain zero records for these asset IDs. It does not determine if logging was disabled on the device or if records were filtered out during submission extraction.",

    submissionId: "SUB-2026-08-CSEX-001",
    contentHashSha3: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    ingestionTimestamp: "2026-08-31T23:59:12Z",
    policyControlExpectation: "NCIIPC Sec 3.1: Mandatory 100% telemetry coverage for designated Critical Information Infrastructure (CII) nodes.",
    detectorVersion: "satsa-worker-negspace:v1.3.1",
    rulesThresholds: "active_inventory_days <= 90, log_count_min=1, asset_tier=1",
    calibrationVersion: "calib-2026.08.1-fin",

    observedFacts: [
      "National CII Registry lists assets SWITCH-PRD-01 through 06 as operational active nodes as of 2026-08-15.",
      "Submitted dataset SUB-2026-08-CSEX-001 contains 1,428,912 records; 0 records match asset IDs SWITCH-PRD-01..06 or DB-PRD-02.",
      "No decommissioning ticket or outage report was submitted for these nodes.",
    ],

    systemInferences: [
      "Syslog forwarding daemon on the management VLAN was either unconfigured, filtered at network boundary, or stopped.",
      "High probability of blind spot in payment routing infrastructure.",
    ],

    recommendedAction: "Request supplemental periodic telemetry export and verification of syslog forwarder daemon status on hosts SWITCH-PRD-01 through 06.",

    reconstructedTimeline: [
      { timestamp: "2026-08-01 00:00:00", step: "Period Start", detail: "Expected telemetry stream window opened.", actorOrSystem: "SAT-SA Engine" },
      { timestamp: "2026-08-31 23:59:12", step: "Submission Ingest", detail: "1,428,912 records ingested; cross-referenced with asset registry.", actorOrSystem: "SAT-SA Normalization" },
      { timestamp: "2026-09-01 02:15:30", step: "Negative Space Evaluation", detail: "Identified 7 Tier-1 assets with expected activity but zero recorded entries.", actorOrSystem: "NegativeSpaceWorker" },
    ],

    evidenceRecords: [
      {
        id: "ev-neg-01",
        alertId: "N/A (Absence)",
        timestampCreated: "2026-08-01T00:00:00Z",
        timestampAck: "N/A",
        timestampClosed: "N/A",
        durationSeconds: 0,
        assetId: "SWITCH-PRD-01",
        assetCriticality: "Tier-1 Critical",
        linkedCaseId: null,
        escalationRecordId: null,
        actorId: "SYSTEM",
        rawJsonSnippet: '{"asset_id":"SWITCH-PRD-01","status":"ACTIVE_IN_INVENTORY","telemetry_records_found":0,"expected_min":50000}',
      },
    ],
  },
  {
    id: "fnd-csey-001",
    findingSlug: "closure-time-faster-than-cohort",
    title: "Closure velocity 4.8× faster than peer cohort median (Metric-gaming anomaly)",
    entitySlug: "cse-y",
    entityName: "CSE-Y (State Grid Dispatch Center)",
    period: "August–September 2026",
    severity: "high",
    confidence: "high",
    findingFamily: "peer_deviation",
    findingFamilyLabel: "Peer Deviation",
    ruleOrCategory: "peer_deviation.closure_velocity",

    observedPattern: "SCADA command validation alerts were closed in a median time of 4.8 minutes, compared to the cohort median of 24.0 minutes. 98.4% of alerts were closed with zero investigative notes.",
    whyThisMatters: "Rapid closures without documented root-cause verification are a standard indicator of SLA metric gaming, where operators prioritize closure volume over verification rigour.",
    
    peerContext: {
      cohortName: "Energy & Power SCADA Cohort",
      cohortMedianPct: 24.0,
      entityObservedPct: 4.8,
      varianceRatio: 5.0,
      description: "Energy & Power SCADA peers take a median of 24 minutes to verify and close telemetry dispatch anomalies. CSE-Y closes comparable alerts in 4.8 minutes.",
    },

    systemLimitation: "Does not prove malice; could be caused by an automated SOAR playbook closing alerts without human intervention. However, no automation execution logs were submitted.",

    submissionId: "SUB-2026-08-CSEY-001",
    contentHashSha3: "91d54f76269b002bc56df69616e1e85ab8f5d5b78e227d8db198c642646d6d87",
    ingestionTimestamp: "2026-09-01T18:30:00Z",
    policyControlExpectation: "NCIIPC Energy Sector Guidelines Sec 5.1: Minimum investigation documentation required for SCADA command mismatch.",
    detectorVersion: "satsa-worker-peerbench:v1.2.0",
    rulesThresholds: "closure_speed_ratio >= 3.0, note_char_count_max <= 20",
    calibrationVersion: "calib-2026.08.1-energy",

    observedFacts: [
      "Median alert triage duration: 288 seconds (4.8 minutes).",
      "98.4% of alert closure notes consist of fewer than 15 characters (e.g. 'ok', 'fp', 'cleared').",
      "Cohort baseline median: 1,440 seconds (24.0 minutes).",
    ],

    systemInferences: [
      "High probability of metric gaming under strict organizational turnaround SLA.",
      "Supervisory risk of overlooked malicious telemetry injections into grid command bus.",
    ],

    recommendedAction: "Mandate procedural audit of dispatch shift operators and review SCADA SOAR playbook configuration.",

    reconstructedTimeline: [
      { timestamp: "2026-08-10 14:20:00", step: "Batch Dispatch Alert", detail: "RTU Command sequence verification alarm.", actorOrSystem: "SCADA IDS" },
      { timestamp: "2026-08-10 14:22:15", step: "Triage Closure", detail: "Closed with note 'ok'. No telemetry packet attached.", actorOrSystem: "Analyst DISP-12" },
      { timestamp: "2026-09-01 18:30:00", step: "Ingestion and Peer Analysis", detail: "Statistical distribution fit reveals 4.8× velocity deviation.", actorOrSystem: "PeerBenchmarkWorker" },
    ],

    evidenceRecords: [
      {
        id: "ev-y-01",
        alertId: "SCADA-AL-882",
        timestampCreated: "2026-08-10T14:20:00Z",
        timestampAck: "2026-08-10T14:21:00Z",
        timestampClosed: "2026-08-10T14:22:15Z",
        durationSeconds: 135,
        assetId: "RTU-SUBSTATION-EAST-4",
        assetCriticality: "Tier-1 Critical",
        linkedCaseId: null,
        escalationRecordId: null,
        actorId: "DISP-12",
        rawJsonSnippet: '{"alert_id":"SCADA-AL-882","rtu_id":"EAST-4","closure_sec":135,"notes":"ok"}',
      },
    ],
  },
];

export const findingById = new Map(findings.map((f) => [f.id, f]));
export const findingBySlug = new Map(findings.map((f) => [f.findingSlug, f]));

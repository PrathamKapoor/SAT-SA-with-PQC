/**
 * SAT-SA NCIIPC Supervisory Workbench: Operational Review Queue
 * Ranks review candidates across entities with explicit reasons for priority,
 * recommended examiner actions, evidence counts, and auditable dispositions.
 */

export type QueuePriority = "critical" | "high" | "medium" | "low";
export type FindingFamily = "execution_gap" | "negative_space" | "anomaly" | "peer_deviation";
export type DispositionType = "open" | "confirmed_concern" | "not_substantiated" | "needs_more_info" | "escalated";

export interface QueueItem {
  id: string;
  rank: number;
  priority: QueuePriority;
  priorityReason: string;
  entitySlug: string;
  entityName: string;
  assetId: string;
  assetName: string;
  alertOrCaseId: string;
  findingFamily: FindingFamily;
  findingFamilyLabel: string;
  findingId: string;
  confidence: "high" | "medium" | "low";
  corroboratingSignalsCount: number;
  corroboratingSignalsDetail: string;
  evidenceCount: number;
  recommendedAction: "INSPECT_INVESTIGATION" | "REQUEST_MISSING_EVIDENCE" | "ISSUE_SUPERVISORY_INQUIRY" | "RECALIBRATE_BASELINE";
  recommendedActionLabel: string;
  assignedExaminer: string;
  reviewDueDate: string;
  currentDisposition: DispositionType;
  dispositionRationale?: string;
  dispositionTimestamp?: string;
  dispositionHistory: {
    id: string;
    disposition: DispositionType;
    rationale: string;
    timestamp: string;
    examiner: string;
    digest: string;
    actionType: "initial_assessment" | "reversal" | "subsequent_correction" | "escalation";
  }[];
}

export const initialQueueItems: QueueItem[] = [
  {
    id: "queue-001",
    rank: 1,
    priority: "critical",
    priorityReason: "Critical alert closed in four minutes with no case/escalation on Tier-1 switchgear.",
    entitySlug: "cse-x",
    entityName: "CSE-X (National Payments Gateway)",
    assetId: "CORE-SWIFT-01",
    assetName: "Core SWIFT Gateway Host #01",
    alertOrCaseId: "AL-1001",
    findingFamily: "execution_gap",
    findingFamilyLabel: "Execution Gap",
    findingId: "fnd-csex-001",
    confidence: "high",
    corroboratingSignalsCount: 18,
    corroboratingSignalsDetail: "18 identical rapid closures across 3 payment switchgear nodes in August window",
    evidenceCount: 18,
    recommendedAction: "INSPECT_INVESTIGATION",
    recommendedActionLabel: "Inspect operator shift logs & terminal capture",
    assignedExaminer: "Examiner A. Sharma (Lead)",
    reviewDueDate: "2026-09-15",
    currentDisposition: "open",
    dispositionHistory: [
      {
        id: "disp-hist-001",
        disposition: "open",
        rationale: "Queue candidate auto-ingested and ranked #1 based on criticality and execution gap risk score.",
        timestamp: "2026-09-01T08:00:00Z",
        examiner: "SAT-SA Engine (Automated Ingest)",
        digest: "a6b98e1f02c918237e890c2a...",
        actionType: "initial_assessment",
      },
    ],
  },
  {
    id: "queue-002",
    rank: 2,
    priority: "critical",
    priorityReason: "Potential metric-gaming pattern: unusually high closure rate with low investigation depth.",
    entitySlug: "cse-y",
    entityName: "CSE-Y (State Grid Dispatch Center)",
    assetId: "RTU-EAST-4",
    assetName: "Substation East-4 Gateway",
    alertOrCaseId: "SCADA-AL-882",
    findingFamily: "peer_deviation",
    findingFamilyLabel: "Peer Deviation",
    findingId: "fnd-csey-001",
    confidence: "high",
    corroboratingSignalsCount: 68,
    corroboratingSignalsDetail: "Closure time 4.8× faster than SCADA cohort median; 98.4% notes <15 chars",
    evidenceCount: 68,
    recommendedAction: "ISSUE_SUPERVISORY_INQUIRY",
    recommendedActionLabel: "Issue supervisory inquiry on triage automation",
    assignedExaminer: "Examiner V. Patel (Senior)",
    reviewDueDate: "2026-09-16",
    currentDisposition: "open",
    dispositionHistory: [
      {
        id: "disp-hist-002",
        disposition: "open",
        rationale: "Candidate flagged due to extreme peer cohort velocity deviation.",
        timestamp: "2026-09-01T08:00:00Z",
        examiner: "SAT-SA Engine (Automated Ingest)",
        digest: "f10b2c3a992e10478a87b1c...",
        actionType: "initial_assessment",
      },
    ],
  },
  {
    id: "queue-003",
    rank: 3,
    priority: "high",
    priorityReason: "Negative-space gap: 7 critical payment assets have zero telemetry submitted across 60 days.",
    entitySlug: "cse-x",
    entityName: "CSE-X (National Payments Gateway)",
    assetId: "SWITCH-PRD-01..06",
    assetName: "Production Core Switches 01-06",
    alertOrCaseId: "SUB-CSEX-NEG-07",
    findingFamily: "negative_space",
    findingFamilyLabel: "Missing Evidence",
    findingId: "fnd-csex-002",
    confidence: "high",
    corroboratingSignalsCount: 7,
    corroboratingSignalsDetail: "Active inventory confirmed by registry; zero syslog lines present",
    evidenceCount: 7,
    recommendedAction: "REQUEST_MISSING_EVIDENCE",
    recommendedActionLabel: "Request supplemental syslog and forwarder daemon status",
    assignedExaminer: "Examiner A. Sharma (Lead)",
    reviewDueDate: "2026-09-17",
    currentDisposition: "open",
    dispositionHistory: [],
  },
  {
    id: "queue-004",
    rank: 4,
    priority: "high",
    priorityReason: "Recurring alert on critical asset with no remediation evidence across 3 cycles.",
    entitySlug: "cse-z",
    entityName: "CSE-Z (National Satellite Telemetry Hub)",
    assetId: "UPLINK-SRV-02",
    assetName: "Earth Station Tracking Demodulator",
    alertOrCaseId: "BGP-HIJACK-AL-41",
    findingFamily: "execution_gap",
    findingFamilyLabel: "Execution Gap",
    findingId: "fnd-csex-001",
    confidence: "medium",
    corroboratingSignalsCount: 6,
    corroboratingSignalsDetail: "6 route flap alarms closed without post-mortem or ASN filter change",
    evidenceCount: 14,
    recommendedAction: "INSPECT_INVESTIGATION",
    recommendedActionLabel: "Inspect peering router configuration diffs",
    assignedExaminer: "Examiner M. Rao",
    reviewDueDate: "2026-09-18",
    currentDisposition: "needs_more_info",
    dispositionRationale: "Requested upstream carrier NOC maintenance confirmation on 2026-09-05.",
    dispositionTimestamp: "2026-09-05T11:20:00Z",
    dispositionHistory: [
      {
        id: "disp-hist-004",
        disposition: "needs_more_info",
        rationale: "Requested upstream carrier NOC maintenance confirmation to verify if route flap was intentional carrier maintenance.",
        timestamp: "2026-09-05T11:20:00Z",
        examiner: "Examiner M. Rao",
        digest: "82bc194a0b29ef...",
        actionType: "subsequent_correction",
      },
    ],
  },
  {
    id: "queue-005",
    rank: 5,
    priority: "medium",
    priorityReason: "Entity has low telemetry coverage (76.5%) compared with peer cohort average (94.2%).",
    entitySlug: "cse-neg",
    entityName: "CSE-NEG (Naval Dockyard Systems)",
    assetId: "DOCK-SUBNET-100",
    assetName: "VLAN 100 Dock switchgear",
    alertOrCaseId: "DATA-QUAL-09",
    findingFamily: "negative_space",
    findingFamilyLabel: "Missing Evidence",
    findingId: "fnd-csex-002",
    confidence: "low",
    corroboratingSignalsCount: 3,
    corroboratingSignalsDetail: "Syslog truncation detected due to collector partition overflow",
    evidenceCount: 3,
    recommendedAction: "REQUEST_MISSING_EVIDENCE",
    recommendedActionLabel: "Request secondary storage archive export",
    assignedExaminer: "Examiner V. Patel",
    reviewDueDate: "2026-09-20",
    currentDisposition: "open",
    dispositionHistory: [],
  },
  {
    id: "queue-006",
    rank: 6,
    priority: "medium",
    priorityReason: "Execution gap: automated closure of USB insertion events on perimeter hosts.",
    entitySlug: "cse-anom",
    entityName: "CSE-ANOM (Defence Ordnance Network)",
    assetId: "MFG-WS-094",
    assetName: "Factory Floor Control Workstation 94",
    alertOrCaseId: "USB-BLOCK-88",
    findingFamily: "execution_gap",
    findingFamilyLabel: "Execution Gap",
    findingId: "fnd-csex-001",
    confidence: "medium",
    corroboratingSignalsCount: 6,
    corroboratingSignalsDetail: "6 events marked false positive without physical custodian register check",
    evidenceCount: 6,
    recommendedAction: "INSPECT_INVESTIGATION",
    recommendedActionLabel: "Verify physical optical ledger scan",
    assignedExaminer: "Examiner M. Rao",
    reviewDueDate: "2026-09-22",
    currentDisposition: "open",
    dispositionHistory: [],
  },
  {
    id: "queue-007",
    rank: 7,
    priority: "low",
    priorityReason: "Privileged access elevation tickets lacking explicit change ticket reference.",
    entitySlug: "cse-exec",
    entityName: "CSE-EXEC (Strategic Heavy Engineering)",
    assetId: "CNC-HOST-01",
    assetName: "CNC Controller Production Unit #01",
    alertOrCaseId: "PRIV-ELEV-12",
    findingFamily: "execution_gap",
    findingFamilyLabel: "Execution Gap",
    findingId: "fnd-csex-001",
    confidence: "medium",
    corroboratingSignalsCount: 7,
    corroboratingSignalsDetail: "Admin elevation occurred during commissioning phase",
    evidenceCount: 7,
    recommendedAction: "RECALIBRATE_BASELINE",
    recommendedActionLabel: "Cross-reference commissioning window authorizations",
    assignedExaminer: "Examiner A. Sharma",
    reviewDueDate: "2026-09-25",
    currentDisposition: "not_substantiated",
    dispositionRationale: "Commissioning authorization approved by Chief Engineer; emergency change ticket verified.",
    dispositionTimestamp: "2026-09-06T15:30:00Z",
    dispositionHistory: [
      {
        id: "disp-hist-007",
        disposition: "not_substantiated",
        rationale: "Commissioning authorization verified via optical disk physical logbook signed by Chief Engineer.",
        timestamp: "2026-09-06T15:30:00Z",
        examiner: "Examiner A. Sharma",
        digest: "33ea8192b0c...",
        actionType: "initial_assessment",
      },
    ],
  },
];

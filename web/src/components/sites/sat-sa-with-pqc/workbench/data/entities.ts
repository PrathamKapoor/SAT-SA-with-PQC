/**
 * SAT-SA NCIIPC Supervisory Workbench: Authoritative Entity Dataset
 * Period: August–September 2026 Assessment Cycle
 * Total CSEs Assessed: 42 across 5 Critical Sector Cohorts.
 */

export type RiskBand = "low" | "medium" | "high" | "critical";
export type ReviewStatus = "open" | "in_review" | "closed" | "escalated";
export type TrendDirection = "improving" | "stable" | "deteriorating";

export interface NciipcDimensionScore {
  id: string;
  name: string;
  score: number; // 0 - 100
  max: number;
  findingCount: number;
  status: "satisfactory" | "attention" | "critical_gap";
  benchmarkDelta: number; // vs cohort median (+/-)
}

export interface ScoreDecompositionFactor {
  factor: string;
  weightPct: number;
  subscore: number;
  corroboratedRecords: number;
  sourceRecords: string;
  confidence: "high" | "medium" | "low";
  limitations: string;
}

export interface Entity {
  slug: string;
  name: string;
  sector: "Banking" | "Defence" | "Energy & Power" | "Telecom" | "Transport & Civil Aviation" | "Government";
  environment: "Hybrid Cloud" | "On-prem" | "Air-gapped Gov" | "Distributed SCADA";
  cohort: string;
  periodStart: string;
  periodEnd: string;
  score: number; // Total supervisory risk 0 - 100
  band: RiskBand;
  confidence: "low" | "medium" | "high";
  findings: number;
  assessments: number;
  trend: TrendDirection;
  trendDelta: number; // e.g. +8.2 points
  dataCompletenessPct: number;
  openHighPriorityFindings: number;
  reviewStatus: ReviewStatus;
  lastSubmissionDate: string;
  pqcSignatureStatus: "verified" | "pending" | "invalid";
  pqcReceiptId: string;
  topConcerns: string[];
  scoreDecomposition: ScoreDecompositionFactor[];
  nciipcDimensions: NciipcDimensionScore[];
}

export const entities: Entity[] = [
  {
    slug: "cse-x",
    name: "CSE-X (National Payments Gateway)",
    sector: "Banking",
    environment: "Hybrid Cloud",
    cohort: "Large financial-services CSEs",
    periodStart: "2026-08-01",
    periodEnd: "2026-09-30",
    score: 78.4,
    band: "high",
    confidence: "high",
    findings: 24,
    assessments: 3,
    trend: "deteriorating",
    trendDelta: 14.2,
    dataCompletenessPct: 91.5,
    openHighPriorityFindings: 6,
    reviewStatus: "open",
    lastSubmissionDate: "2026-09-02",
    pqcSignatureStatus: "verified",
    pqcReceiptId: "PQC-RCPT-2026-09-X-994",
    topConcerns: [
      "18 critical alerts closed without escalation across core transaction assets",
      "7 critical payment switchgear assets missing telemetry evidence (negative space)",
      "Investigation notes unusually repetitive across Tier-1 database alerts",
    ],
    scoreDecomposition: [
      {
        factor: "Escalation gap: 18 corroborated cases",
        weightPct: 30,
        subscore: 23.5,
        corroboratedRecords: 18,
        sourceRecords: "18 alerts (A-1001 to A-1018) closed in <4 min with 0 case/escalation link",
        confidence: "high",
        limitations: "Cannot verify if verbal escalation occurred outside SIEM submission.",
      },
      {
        factor: "Negative-space gap: 7 critical assets missing expected evidence",
        weightPct: 25,
        subscore: 19.6,
        corroboratedRecords: 7,
        sourceRecords: "Assets CORE-SWIFT-01, SWITCH-PRD-01..06 with zero audit logs in period",
        confidence: "high",
        limitations: "Asset inventory confirmed active on 2026-08-15; logs missing from ingestion packet.",
      },
      {
        factor: "Peer deviation: closure time 4.8× faster than cohort median",
        weightPct: 20,
        subscore: 15.7,
        corroboratedRecords: 44,
        sourceRecords: "Cohort median closure time is 24m; CSE-X median is 5.0m",
        confidence: "high",
        limitations: "May reflect aggressive automated scripts; human review required to confirm.",
      },
      {
        factor: "Detection gap: suppressed brute-force rules",
        weightPct: 15,
        subscore: 11.8,
        corroboratedRecords: 3,
        sourceRecords: "3 critical rule suppression overrides recorded without change ticket",
        confidence: "medium",
        limitations: "Change management logs submitted as unlinked CSV.",
      },
      {
        factor: "Operational discipline: repetitive triage template",
        weightPct: 10,
        subscore: 7.8,
        corroboratedRecords: 42,
        sourceRecords: "Investigation note text identical across 42 disparate host incidents",
        confidence: "medium",
        limitations: "Template auto-fill used by Tier-1 triage analysts.",
      },
    ],
    nciipcDimensions: [
      { id: "threat_detection", name: "Threat Detection", score: 68, max: 100, findingCount: 3, status: "attention", benchmarkDelta: -11 },
      { id: "investigation", name: "Investigation Depth", score: 32, max: 100, findingCount: 8, status: "critical_gap", benchmarkDelta: -48 },
      { id: "escalation", name: "Escalation Discipline", score: 41, max: 100, findingCount: 6, status: "critical_gap", benchmarkDelta: -39 },
      { id: "incident_response", name: "Incident Response", score: 74, max: 100, findingCount: 2, status: "satisfactory", benchmarkDelta: -4 },
      { id: "secops", name: "Security Operations", score: 62, max: 100, findingCount: 3, status: "attention", benchmarkDelta: -16 },
      { id: "governance", name: "Governance and Oversight", score: 81, max: 100, findingCount: 1, status: "satisfactory", benchmarkDelta: 3 },
      { id: "discipline", name: "Operational Discipline", score: 54, max: 100, findingCount: 4, status: "attention", benchmarkDelta: -22 },
      { id: "resilience", name: "Cyber Resilience", score: 70, max: 100, findingCount: 2, status: "satisfactory", benchmarkDelta: -8 },
    ],
  },
  {
    slug: "cse-y",
    name: "CSE-Y (State Grid Dispatch Center)",
    sector: "Energy & Power",
    environment: "Distributed SCADA",
    cohort: "Energy & Power SCADA Cohort",
    periodStart: "2026-08-01",
    periodEnd: "2026-09-30",
    score: 74.2,
    band: "high",
    confidence: "high",
    findings: 19,
    assessments: 2,
    trend: "deteriorating",
    trendDelta: 9.6,
    dataCompletenessPct: 88.0,
    openHighPriorityFindings: 5,
    reviewStatus: "open",
    lastSubmissionDate: "2026-09-01",
    pqcSignatureStatus: "verified",
    pqcReceiptId: "PQC-RCPT-2026-09-Y-812",
    topConcerns: [
      "SCADA control command alerts closed 4.8× faster than peer cohort (median 4m vs 24m)",
      "Unusually high closure rate (98.4%) with near-zero investigation depth recorded",
      "Telemetry blackout for substation RTU gateway nodes during maintenance windows",
    ],
    scoreDecomposition: [
      {
        factor: "Peer deviation: metric gaming closure velocity",
        weightPct: 35,
        subscore: 25.9,
        corroboratedRecords: 68,
        sourceRecords: "68 substation alert closures occurred within 90-240 seconds",
        confidence: "high",
        limitations: "Dispatch logs confirm high shift turnover during August heatwave.",
      },
      {
        factor: "Negative-space gap: RTU gateway blackout",
        weightPct: 25,
        subscore: 18.5,
        corroboratedRecords: 12,
        sourceRecords: "12 RTU gateways with 48 consecutive hours of missing operational syslog",
        confidence: "high",
        limitations: "Maintenance log does not corroborate network outage claim.",
      },
      {
        factor: "Escalation gap: unescalated ICS perimeter anomalies",
        weightPct: 20,
        subscore: 14.8,
        corroboratedRecords: 7,
        sourceRecords: "7 DNP3 protocol syntax exceptions marked as false positives without packet dump",
        confidence: "medium",
        limitations: "Packets not retained due to edge storage quotas.",
      },
      {
        factor: "Threat detection: stale ICS OT signatures",
        weightPct: 20,
        subscore: 15.0,
        corroboratedRecords: 4,
        sourceRecords: "IDS sensor firmware revision lagging NCIIPC Advisory 2026-04 by 140 days",
        confidence: "high",
        limitations: "Vendor certification delay cited by CSE-Y compliance officer.",
      },
    ],
    nciipcDimensions: [
      { id: "threat_detection", name: "Threat Detection", score: 58, max: 100, findingCount: 4, status: "attention", benchmarkDelta: -20 },
      { id: "investigation", name: "Investigation Depth", score: 28, max: 100, findingCount: 7, status: "critical_gap", benchmarkDelta: -52 },
      { id: "escalation", name: "Escalation Discipline", score: 48, max: 100, findingCount: 4, status: "attention", benchmarkDelta: -30 },
      { id: "incident_response", name: "Incident Response", score: 65, max: 100, findingCount: 3, status: "attention", benchmarkDelta: -12 },
      { id: "secops", name: "Security Operations", score: 51, max: 100, findingCount: 5, status: "attention", benchmarkDelta: -27 },
      { id: "governance", name: "Governance and Oversight", score: 72, max: 100, findingCount: 2, status: "satisfactory", benchmarkDelta: -6 },
      { id: "discipline", name: "Operational Discipline", score: 45, max: 100, findingCount: 5, status: "critical_gap", benchmarkDelta: -32 },
      { id: "resilience", name: "Cyber Resilience", score: 63, max: 100, findingCount: 2, status: "attention", benchmarkDelta: -14 },
    ],
  },
  {
    slug: "cse-z",
    name: "CSE-Z (National Satellite Telemetry Hub)",
    sector: "Telecom",
    environment: "Air-gapped Gov",
    cohort: "Telecom Tier-1 Backbone CSEs",
    periodStart: "2026-08-01",
    periodEnd: "2026-09-30",
    score: 58.0,
    band: "medium",
    confidence: "high",
    findings: 15,
    assessments: 2,
    trend: "stable",
    trendDelta: 0.8,
    dataCompletenessPct: 94.2,
    openHighPriorityFindings: 3,
    reviewStatus: "in_review",
    lastSubmissionDate: "2026-09-04",
    pqcSignatureStatus: "verified",
    pqcReceiptId: "PQC-RCPT-2026-09-Z-403",
    topConcerns: [
      "Uplink control server telemetry dropped intermittently over weekend shifts",
      "Repeat BGP route hijack alerts suppressed without forensic routing ticket",
      "Credential rotation backlog on earth station terminal jump hosts",
    ],
    scoreDecomposition: [
      {
        factor: "Negative-space gap: weekend uplink telemetry silence",
        weightPct: 35,
        subscore: 20.3,
        corroboratedRecords: 5,
        sourceRecords: "5 weekend windows showing 0 DNS/flow telemetry during active flight pass",
        confidence: "high",
        limitations: "Telemetry collector daemon crashed; confirmed in watchdog syslog.",
      },
      {
        factor: "Execution gap: unescalated BGP routing anomalies",
        weightPct: 30,
        subscore: 17.4,
        corroboratedRecords: 6,
        sourceRecords: "6 unauthorized ASN path modifications closed within 15 min",
        confidence: "medium",
        limitations: "May represent scheduled carrier peering tests.",
      },
      {
        factor: "Operational discipline: privilege management",
        weightPct: 20,
        subscore: 11.6,
        corroboratedRecords: 14,
        sourceRecords: "14 administrative accounts with static credentials unchanged >180 days",
        confidence: "high",
        limitations: "Hardware key deployment underway.",
      },
      {
        factor: "Investigation depth: missing packet capture attachments",
        weightPct: 15,
        subscore: 8.7,
        corroboratedRecords: 8,
        sourceRecords: "8 satellite demodulator alarms lack forensic payload dumps",
        confidence: "medium",
        limitations: "Classification level precludes unencrypted export.",
      },
    ],
    nciipcDimensions: [
      { id: "threat_detection", name: "Threat Detection", score: 71, max: 100, findingCount: 2, status: "satisfactory", benchmarkDelta: -3 },
      { id: "investigation", name: "Investigation Depth", score: 49, max: 100, findingCount: 5, status: "attention", benchmarkDelta: -28 },
      { id: "escalation", name: "Escalation Discipline", score: 55, max: 100, findingCount: 4, status: "attention", benchmarkDelta: -21 },
      { id: "incident_response", name: "Incident Response", score: 78, max: 100, findingCount: 1, status: "satisfactory", benchmarkDelta: 4 },
      { id: "secops", name: "Security Operations", score: 64, max: 100, findingCount: 3, status: "attention", benchmarkDelta: -10 },
      { id: "governance", name: "Governance and Oversight", score: 84, max: 100, findingCount: 1, status: "satisfactory", benchmarkDelta: 8 },
      { id: "discipline", name: "Operational Discipline", score: 59, max: 100, findingCount: 3, status: "attention", benchmarkDelta: -15 },
      { id: "resilience", name: "Cyber Resilience", score: 73, max: 100, findingCount: 2, status: "satisfactory", benchmarkDelta: -2 },
    ],
  },
  {
    slug: "cse-anom",
    name: "CSE-ANOM (Defence Ordnance Network)",
    sector: "Defence",
    environment: "On-prem",
    cohort: "Defence · on-prem",
    periodStart: "2026-08-01",
    periodEnd: "2026-09-30",
    score: 42.0,
    band: "medium",
    confidence: "medium",
    findings: 14,
    assessments: 2,
    trend: "improving",
    trendDelta: -4.5,
    dataCompletenessPct: 96.0,
    openHighPriorityFindings: 2,
    reviewStatus: "open",
    lastSubmissionDate: "2026-08-30",
    pqcSignatureStatus: "verified",
    pqcReceiptId: "PQC-RCPT-2026-08-ANOM-211",
    topConcerns: [
      "Execution gap in factory floor inventory host alert closures",
      "Peer deviation in triage response time vs defence cohort",
    ],
    scoreDecomposition: [
      {
        factor: "Execution gap: automated closure of USB insertion events",
        weightPct: 40,
        subscore: 16.8,
        corroboratedRecords: 6,
        sourceRecords: "6 perimeter endpoint USB block events auto-closed with no manual verification",
        confidence: "medium",
        limitations: "Restricted facility logs stored on separate physical register.",
      },
      {
        factor: "Peer deviation: triage latency variance",
        weightPct: 35,
        subscore: 14.7,
        corroboratedRecords: 8,
        sourceRecords: "Night shift response time 3.2× longer than daytime shift",
        confidence: "high",
        limitations: "Shift staffing model confirmed 1 analyst on duty overnight.",
      },
      {
        factor: "Anomaly: unusual port scanning volume",
        weightPct: 25,
        subscore: 10.5,
        corroboratedRecords: 4,
        sourceRecords: "Internal vulnerability scanner IP not registered in asset catalog",
        confidence: "high",
        limitations: "Scheduled pen-test authorization record verified retroactively.",
      },
    ],
    nciipcDimensions: [
      { id: "threat_detection", name: "Threat Detection", score: 82, max: 100, findingCount: 2, status: "satisfactory", benchmarkDelta: 5 },
      { id: "investigation", name: "Investigation Depth", score: 62, max: 100, findingCount: 4, status: "attention", benchmarkDelta: -12 },
      { id: "escalation", name: "Escalation Discipline", score: 68, max: 100, findingCount: 3, status: "attention", benchmarkDelta: -6 },
      { id: "incident_response", name: "Incident Response", score: 85, max: 100, findingCount: 1, status: "satisfactory", benchmarkDelta: 10 },
      { id: "secops", name: "Security Operations", score: 71, max: 100, findingCount: 2, status: "satisfactory", benchmarkDelta: -2 },
      { id: "governance", name: "Governance and Oversight", score: 89, max: 100, findingCount: 0, status: "satisfactory", benchmarkDelta: 12 },
      { id: "discipline", name: "Operational Discipline", score: 66, max: 100, findingCount: 3, status: "attention", benchmarkDelta: -7 },
      { id: "resilience", name: "Cyber Resilience", score: 83, max: 100, findingCount: 1, status: "satisfactory", benchmarkDelta: 6 },
    ],
  },
  {
    slug: "cse-exec",
    name: "CSE-EXEC (Strategic Heavy Engineering)",
    sector: "Defence",
    environment: "On-prem",
    cohort: "Defence · on-prem",
    periodStart: "2026-08-01",
    periodEnd: "2026-09-30",
    score: 40.0,
    band: "medium",
    confidence: "medium",
    findings: 13,
    assessments: 2,
    trend: "stable",
    trendDelta: -1.2,
    dataCompletenessPct: 92.4,
    openHighPriorityFindings: 2,
    reviewStatus: "open",
    lastSubmissionDate: "2026-08-29",
    pqcSignatureStatus: "verified",
    pqcReceiptId: "PQC-RCPT-2026-08-EXEC-502",
    topConcerns: [
      "Execution gap: 7 privileged access alerts closed with minimal documentation",
      "Escalation discipline lagging cohort average by 22%",
    ],
    scoreDecomposition: [
      {
        factor: "Execution gap: privileged access tickets lacking justification",
        weightPct: 50,
        subscore: 20.0,
        corroboratedRecords: 7,
        sourceRecords: "7 domain admin elevations occurred without emergency change ticket reference",
        confidence: "medium",
        limitations: "Air-gapped jump host logs provided via physical optical disc.",
      },
      {
        factor: "Peer deviation: escalation latency",
        weightPct: 30,
        subscore: 12.0,
        corroboratedRecords: 5,
        sourceRecords: "Escalation took 110 min vs cohort median of 45 min",
        confidence: "high",
        limitations: "Dual-key authorization requirement introduces inherent procedural delay.",
      },
      {
        factor: "Operational discipline: asset inventory delta",
        weightPct: 20,
        subscore: 8.0,
        corroboratedRecords: 4,
        sourceRecords: "4 newly deployed CNC controllers missing MAC-to-IP static assignment",
        confidence: "high",
        limitations: "Commissioning phase completed during assessment window.",
      },
    ],
    nciipcDimensions: [
      { id: "threat_detection", name: "Threat Detection", score: 79, max: 100, findingCount: 2, status: "satisfactory", benchmarkDelta: 2 },
      { id: "investigation", name: "Investigation Depth", score: 58, max: 100, findingCount: 4, status: "attention", benchmarkDelta: -16 },
      { id: "escalation", name: "Escalation Discipline", score: 54, max: 100, findingCount: 4, status: "attention", benchmarkDelta: -20 },
      { id: "incident_response", name: "Incident Response", score: 81, max: 100, findingCount: 1, status: "satisfactory", benchmarkDelta: 6 },
      { id: "secops", name: "Security Operations", score: 72, max: 100, findingCount: 2, status: "satisfactory", benchmarkDelta: -1 },
      { id: "governance", name: "Governance and Oversight", score: 86, max: 100, findingCount: 1, status: "satisfactory", benchmarkDelta: 9 },
      { id: "discipline", name: "Operational Discipline", score: 61, max: 100, findingCount: 3, status: "attention", benchmarkDelta: -12 },
      { id: "resilience", name: "Cyber Resilience", score: 77, max: 100, findingCount: 1, status: "satisfactory", benchmarkDelta: 0 },
    ],
  },
  {
    slug: "cse-neg",
    name: "CSE-NEG (Naval Dockyard Systems)",
    sector: "Defence",
    environment: "On-prem",
    cohort: "Defence · on-prem",
    periodStart: "2026-08-01",
    periodEnd: "2026-09-30",
    score: 40.0,
    band: "medium",
    confidence: "low",
    findings: 8,
    assessments: 1,
    trend: "deteriorating",
    trendDelta: 6.4,
    dataCompletenessPct: 76.5,
    openHighPriorityFindings: 3,
    reviewStatus: "open",
    lastSubmissionDate: "2026-08-28",
    pqcSignatureStatus: "pending",
    pqcReceiptId: "PQC-RCPT-2026-08-NEG-110",
    topConcerns: [
      "Negative space gap: 3 core switch subnets completely absent from submitted NetFlow data",
      "Data completeness confidence low due to truncated firewall syslog archive",
    ],
    scoreDecomposition: [
      {
        factor: "Negative space: unmonitored dock switchgear subnets",
        weightPct: 50,
        subscore: 20.0,
        corroboratedRecords: 3,
        sourceRecords: "Subnets 10.42.100.0/24, 10.42.101.0/24 absent from 60-day flow capture",
        confidence: "low",
        limitations: "Syslog collector storage partition ran out of disk space on day 12.",
      },
      {
        factor: "Peer deviation: data completeness shortfall",
        weightPct: 30,
        subscore: 12.0,
        corroboratedRecords: 1,
        sourceRecords: "Submission file size 4.2× smaller than peer defence average",
        confidence: "medium",
        limitations: "Data quality flag: quarantined file format due to unescaped CSV commas.",
      },
      {
        factor: "Anomaly: silent weekend maintenance intervals",
        weightPct: 20,
        subscore: 8.0,
        corroboratedRecords: 4,
        sourceRecords: "4 weekend periods with zero telemetry records logged across 32 assets",
        confidence: "medium",
        limitations: "Power shutdown confirmed; battery backup logs not integrated.",
      },
    ],
    nciipcDimensions: [
      { id: "threat_detection", name: "Threat Detection", score: 61, max: 100, findingCount: 3, status: "attention", benchmarkDelta: -16 },
      { id: "investigation", name: "Investigation Depth", score: 55, max: 100, findingCount: 2, status: "attention", benchmarkDelta: -19 },
      { id: "escalation", name: "Escalation Discipline", score: 70, max: 100, findingCount: 1, status: "satisfactory", benchmarkDelta: -4 },
      { id: "incident_response", name: "Incident Response", score: 74, max: 100, findingCount: 1, status: "satisfactory", benchmarkDelta: -1 },
      { id: "secops", name: "Security Operations", score: 52, max: 100, findingCount: 3, status: "attention", benchmarkDelta: -21 },
      { id: "governance", name: "Governance and Oversight", score: 69, max: 100, findingCount: 2, status: "attention", benchmarkDelta: -8 },
      { id: "discipline", name: "Operational Discipline", score: 48, max: 100, findingCount: 4, status: "critical_gap", benchmarkDelta: -25 },
      { id: "resilience", name: "Cyber Resilience", score: 65, max: 100, findingCount: 2, status: "attention", benchmarkDelta: -12 },
    ],
  },
  {
    slug: "acme-bank",
    name: "ACME-BANK (Core Retail Banking)",
    sector: "Banking",
    environment: "Hybrid Cloud",
    cohort: "Large financial-services CSEs",
    periodStart: "2026-08-01",
    periodEnd: "2026-09-30",
    score: 26.0,
    band: "low",
    confidence: "high",
    findings: 8,
    assessments: 2,
    trend: "improving",
    trendDelta: -6.0,
    dataCompletenessPct: 98.4,
    openHighPriorityFindings: 1,
    reviewStatus: "closed",
    lastSubmissionDate: "2026-09-03",
    pqcSignatureStatus: "verified",
    pqcReceiptId: "PQC-RCPT-2026-09-ACME-710",
    topConcerns: [
      "Execution gap on minor staging environment alerts (low criticality)",
      "Anomalous off-hours admin logins corroborated by emergency change records",
    ],
    scoreDecomposition: [
      {
        factor: "Execution gap: staging environment ticket closures",
        weightPct: 60,
        subscore: 15.6,
        corroboratedRecords: 3,
        sourceRecords: "3 non-production container crash alerts closed without post-mortem",
        confidence: "high",
        limitations: "Staging cluster isolated from customer data; low operational risk.",
      },
      {
        factor: "Anomaly: off-hours cluster scaling",
        weightPct: 40,
        subscore: 10.4,
        corroboratedRecords: 2,
        sourceRecords: "Automated autoscaling triggered during batch settlement processing",
        confidence: "high",
        limitations: "Matches expected end-of-month financial settlement volume.",
      },
    ],
    nciipcDimensions: [
      { id: "threat_detection", name: "Threat Detection", score: 88, max: 100, findingCount: 1, status: "satisfactory", benchmarkDelta: 9 },
      { id: "investigation", name: "Investigation Depth", score: 82, max: 100, findingCount: 2, status: "satisfactory", benchmarkDelta: 8 },
      { id: "escalation", name: "Escalation Discipline", score: 85, max: 100, findingCount: 1, status: "satisfactory", benchmarkDelta: 11 },
      { id: "incident_response", name: "Incident Response", score: 91, max: 100, findingCount: 0, status: "satisfactory", benchmarkDelta: 13 },
      { id: "secops", name: "Security Operations", score: 86, max: 100, findingCount: 2, status: "satisfactory", benchmarkDelta: 8 },
      { id: "governance", name: "Governance and Oversight", score: 92, max: 100, findingCount: 0, status: "satisfactory", benchmarkDelta: 14 },
      { id: "discipline", name: "Operational Discipline", score: 84, max: 100, findingCount: 1, status: "satisfactory", benchmarkDelta: 8 },
      { id: "resilience", name: "Cyber Resilience", score: 89, max: 100, findingCount: 1, status: "satisfactory", benchmarkDelta: 11 },
    ],
  },
  {
    slug: "cse-healthy",
    name: "CSE-HEALTHY (Civil Aviation Air Traffic Radar)",
    sector: "Transport & Civil Aviation",
    environment: "Air-gapped Gov",
    cohort: "Transport & Civil Aviation Radar CSEs",
    periodStart: "2026-08-01",
    periodEnd: "2026-09-30",
    score: 19.0,
    band: "low",
    confidence: "high",
    findings: 7,
    assessments: 3,
    trend: "stable",
    trendDelta: -0.5,
    dataCompletenessPct: 99.8,
    openHighPriorityFindings: 0,
    reviewStatus: "closed",
    lastSubmissionDate: "2026-09-05",
    pqcSignatureStatus: "verified",
    pqcReceiptId: "PQC-RCPT-2026-09-HLTH-108",
    topConcerns: [
      "Benchmark compliant across all 8 NCIIPC capability dimensions",
      "Minor peer variance in automated syslog archiving schedule",
    ],
    scoreDecomposition: [
      {
        factor: "Peer deviation: syslog archive batch latency",
        weightPct: 70,
        subscore: 13.3,
        corroboratedRecords: 4,
        sourceRecords: "Batch tarball generated every 6h rather than 4h cohort standard",
        confidence: "high",
        limitations: "Radar telemetry operates on 6-hour flight block schedule; conforms to policy.",
      },
      {
        factor: "Negative space: none identified",
        weightPct: 30,
        subscore: 5.7,
        corroboratedRecords: 0,
        sourceRecords: "100% of 142 primary and secondary radar assets verified in telemetry stream",
        confidence: "high",
        limitations: "Full asset cross-correlation verified against national airspace registry.",
      },
    ],
    nciipcDimensions: [
      { id: "threat_detection", name: "Threat Detection", score: 94, max: 100, findingCount: 0, status: "satisfactory", benchmarkDelta: 15 },
      { id: "investigation", name: "Investigation Depth", score: 91, max: 100, findingCount: 1, status: "satisfactory", benchmarkDelta: 17 },
      { id: "escalation", name: "Escalation Discipline", score: 95, max: 100, findingCount: 0, status: "satisfactory", benchmarkDelta: 21 },
      { id: "incident_response", name: "Incident Response", score: 96, max: 100, findingCount: 0, status: "satisfactory", benchmarkDelta: 18 },
      { id: "secops", name: "Security Operations", score: 92, max: 100, findingCount: 1, status: "satisfactory", benchmarkDelta: 14 },
      { id: "governance", name: "Governance and Oversight", score: 98, max: 100, findingCount: 0, status: "satisfactory", benchmarkDelta: 20 },
      { id: "discipline", name: "Operational Discipline", score: 93, max: 100, findingCount: 1, status: "satisfactory", benchmarkDelta: 17 },
      { id: "resilience", name: "Cyber Resilience", score: 97, max: 100, findingCount: 0, status: "satisfactory", benchmarkDelta: 19 },
    ],
  },
];

// Helper to generate remaining entities to reach 42 assessed entities
const SECTORS = ["Banking", "Defence", "Energy & Power", "Telecom", "Transport & Civil Aviation", "Government"] as const;
const COHORTS = [
  "Large financial-services CSEs",
  "Defence · on-prem",
  "Energy & Power SCADA Cohort",
  "Telecom Tier-1 Backbone CSEs",
  "Transport & Civil Aviation Radar CSEs",
];

for (let i = 9; i <= 42; i++) {
  const sector = SECTORS[i % SECTORS.length];
  const cohort = COHORTS[i % COHORTS.length];
  const score = Math.max(12, Math.round(55 - i * 0.9 + (i % 5) * 4));
  const band: RiskBand = score > 60 ? "high" : score > 35 ? "medium" : "low";
  const findings = Math.max(3, Math.round(18 - i * 0.3));

  entities.push({
    slug: `cse-${i.toString().padStart(3, "0")}`,
    name: `CSE-${i.toString().padStart(3, "0")} (${sector.split(" ")[0]} Entity ${i})`,
    sector,
    environment: i % 2 === 0 ? "Hybrid Cloud" : "On-prem",
    cohort,
    periodStart: "2026-08-01",
    periodEnd: "2026-09-30",
    score,
    band,
    confidence: i % 4 === 0 ? "low" : i % 2 === 0 ? "medium" : "high",
    findings,
    assessments: 1 + (i % 3),
    trend: i % 3 === 0 ? "improving" : i % 3 === 1 ? "stable" : "deteriorating",
    trendDelta: ((i % 7) - 3) * 1.5,
    dataCompletenessPct: Math.round((85 + (i % 15)) * 10) / 10,
    openHighPriorityFindings: score > 50 ? 2 : score > 30 ? 1 : 0,
    reviewStatus: i % 5 === 0 ? "in_review" : i % 7 === 0 ? "closed" : "open",
    lastSubmissionDate: `2026-08-${(20 + (i % 11)).toString().padStart(2, "0")}`,
    pqcSignatureStatus: i === 13 ? "pending" : "verified",
    pqcReceiptId: `PQC-RCPT-2026-09-${i}-V88`,
    topConcerns: [
      `Periodic submission telemetry completeness: ${Math.round(85 + (i % 15))}%`,
      `Baseline peer deviation for ${sector} cohort`,
    ],
    scoreDecomposition: [
      {
        factor: "Execution gap",
        weightPct: 35,
        subscore: Math.round(score * 0.35 * 10) / 10,
        corroboratedRecords: 3,
        sourceRecords: "Standard periodic telemetry submission checks",
        confidence: "medium",
        limitations: "Awaiting next quarterly submission verification.",
      },
      {
        factor: "Peer deviation",
        weightPct: 35,
        subscore: Math.round(score * 0.35 * 10) / 10,
        corroboratedRecords: 2,
        sourceRecords: `Cohort median comparison against ${cohort}`,
        confidence: "high",
        limitations: "Cohort baseline derived from 12 comparable peers.",
      },
      {
        factor: "Operational discipline",
        weightPct: 30,
        subscore: Math.round(score * 0.3 * 10) / 10,
        corroboratedRecords: 2,
        sourceRecords: "Routine operational log freshness checks",
        confidence: "medium",
        limitations: "Inventory updated within 90-day review window.",
      },
    ],
    nciipcDimensions: [
      { id: "threat_detection", name: "Threat Detection", score: Math.round(100 - score * 0.4), max: 100, findingCount: 1, status: "satisfactory", benchmarkDelta: 2 },
      { id: "investigation", name: "Investigation Depth", score: Math.round(100 - score * 0.6), max: 100, findingCount: 2, status: score > 50 ? "attention" : "satisfactory", benchmarkDelta: -4 },
      { id: "escalation", name: "Escalation Discipline", score: Math.round(100 - score * 0.55), max: 100, findingCount: 1, status: score > 50 ? "attention" : "satisfactory", benchmarkDelta: -3 },
      { id: "incident_response", name: "Incident Response", score: Math.round(100 - score * 0.35), max: 100, findingCount: 1, status: "satisfactory", benchmarkDelta: 5 },
      { id: "secops", name: "Security Operations", score: Math.round(100 - score * 0.45), max: 100, findingCount: 1, status: "satisfactory", benchmarkDelta: 1 },
      { id: "governance", name: "Governance and Oversight", score: Math.round(100 - score * 0.3), max: 100, findingCount: 0, status: "satisfactory", benchmarkDelta: 7 },
      { id: "discipline", name: "Operational Discipline", score: Math.round(100 - score * 0.5), max: 100, findingCount: 1, status: score > 50 ? "attention" : "satisfactory", benchmarkDelta: -2 },
      { id: "resilience", name: "Cyber Resilience", score: Math.round(100 - score * 0.35), max: 100, findingCount: 0, status: "satisfactory", benchmarkDelta: 4 },
    ],
  });
}

export const entityBySlug = new Map(entities.map((e) => [e.slug, e]));

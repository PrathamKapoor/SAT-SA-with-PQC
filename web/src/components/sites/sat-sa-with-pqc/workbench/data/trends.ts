/**
 * SAT-SA NCIIPC Supervisory Workbench: Trends & Benchmarks Data
 * Multi-cycle time-series, peer distributions, cohort comparability criteria.
 */

export interface CohortProfile {
  cohortId: string;
  name: string;
  sector: string;
  memberCount: number;
  comparabilityCriteria: {
    sectorScope: string;
    assetScale: string;
    criticalityMix: string;
    architectureType: string;
    reportingPeriod: string;
  };
  metrics: {
    closureTimeMedianMinutes: number;
    escalationRatePct: number;
    investigationDepthScore: number;
    telemetryCompletenessPct: number;
    repeatAlertRatePct: number;
  };
}

export const cohorts: CohortProfile[] = [
  {
    cohortId: "cohort-fin-large",
    name: "Large Financial-Services CSEs",
    sector: "Banking & Financial Infrastructure",
    memberCount: 14,
    comparabilityCriteria: {
      sectorScope: "Tier-1 Scheduled Commercial Banks & Clearing Houses",
      assetScale: ">50,000 endpoint/server nodes; >10M daily transaction ops",
      criticalityMix: "High density of SWIFT, RTGS, and Core Banking DB assets",
      architectureType: "Hybrid Cloud with air-gapped hardware security modules",
      reportingPeriod: "August–September 2026 (bi-monthly cycle)",
    },
    metrics: {
      closureTimeMedianMinutes: 24.0,
      escalationRatePct: 97.9,
      investigationDepthScore: 82.5,
      telemetryCompletenessPct: 98.2,
      repeatAlertRatePct: 4.8,
    },
  },
  {
    cohortId: "cohort-energy-scada",
    name: "Energy & Power SCADA Cohort",
    sector: "Energy & Power Transmission",
    memberCount: 9,
    comparabilityCriteria: {
      sectorScope: "Regional Load Despatch Centres & Generation Transmission Grids",
      assetScale: ">1,200 Substation RTUs; DNP3/IEC-60870 protocols",
      criticalityMix: "Tier-1 SCADA dispatch switches and turbine governor nodes",
      architectureType: "Distributed OT with isolated fiber interconnects",
      reportingPeriod: "August–September 2026 (bi-monthly cycle)",
    },
    metrics: {
      closureTimeMedianMinutes: 24.0,
      escalationRatePct: 94.2,
      investigationDepthScore: 74.0,
      telemetryCompletenessPct: 95.8,
      repeatAlertRatePct: 6.2,
    },
  },
  {
    cohortId: "cohort-defence-onprem",
    name: "Defence & Strategic Manufacturing",
    sector: "Defence",
    memberCount: 11,
    comparabilityCriteria: {
      sectorScope: "Defence Public Sector Undertakings & Strategic Ordnance Facilities",
      assetScale: ">15,000 air-gapped endpoints; dedicated factory networks",
      criticalityMix: "CNC production controllers, missile telemetry, and naval drydocks",
      architectureType: "Pure on-premise air-gapped with optical diode transfer",
      reportingPeriod: "August–September 2026 (bi-monthly cycle)",
    },
    metrics: {
      closureTimeMedianMinutes: 45.0,
      escalationRatePct: 96.5,
      investigationDepthScore: 78.0,
      telemetryCompletenessPct: 92.5,
      repeatAlertRatePct: 3.5,
    },
  },
  {
    cohortId: "cohort-telecom-tier1",
    name: "Telecom Tier-1 Backbone CSEs",
    sector: "Telecommunications",
    memberCount: 8,
    comparabilityCriteria: {
      sectorScope: "National Tier-1 Internet Service Providers & Satellite Ground Stations",
      assetScale: ">100,000 edge routers; 400G DWDM optical rings",
      criticalityMix: "BGP route reflectors, lawful intercept switches, DNS root mirrors",
      architectureType: "Nationwide high-throughput distributed carrier fabric",
      reportingPeriod: "August–September 2026 (bi-monthly cycle)",
    },
    metrics: {
      closureTimeMedianMinutes: 18.5,
      escalationRatePct: 98.1,
      investigationDepthScore: 80.0,
      telemetryCompletenessPct: 97.4,
      repeatAlertRatePct: 7.1,
    },
  },
];

export interface TimeSeriesPoint {
  period: string; // e.g. "Mar 2026", "Apr 2026", ...
  csexValue: number;
  cseyValue: number;
  cohortMedian: number;
  sectorBaseline: number;
}

export const closureTimeTrend: TimeSeriesPoint[] = [
  { period: "Mar 2026", csexValue: 22.4, cseyValue: 21.0, cohortMedian: 23.5, sectorBaseline: 25.0 },
  { period: "Apr 2026", csexValue: 19.8, cseyValue: 18.2, cohortMedian: 24.0, sectorBaseline: 25.2 },
  { period: "May 2026", csexValue: 16.2, cseyValue: 14.5, cohortMedian: 23.8, sectorBaseline: 24.8 },
  { period: "Jun 2026", csexValue: 12.0, cseyValue: 9.8, cohortMedian: 24.2, sectorBaseline: 25.0 },
  { period: "Jul 2026", csexValue: 7.5, cseyValue: 6.2, cohortMedian: 24.0, sectorBaseline: 24.9 },
  { period: "Aug 2026", csexValue: 5.0, cseyValue: 4.8, cohortMedian: 24.0, sectorBaseline: 25.0 },
  { period: "Sep 2026", csexValue: 4.9, cseyValue: 4.6, cohortMedian: 24.1, sectorBaseline: 25.1 },
];

export const escalationRateTrend: TimeSeriesPoint[] = [
  { period: "Mar 2026", csexValue: 96.2, cseyValue: 94.0, cohortMedian: 97.5, sectorBaseline: 96.0 },
  { period: "Apr 2026", csexValue: 92.4, cseyValue: 91.5, cohortMedian: 97.8, sectorBaseline: 96.2 },
  { period: "May 2026", csexValue: 88.0, cseyValue: 85.2, cohortMedian: 97.9, sectorBaseline: 96.0 },
  { period: "Jun 2026", csexValue: 81.5, cseyValue: 79.0, cohortMedian: 98.0, sectorBaseline: 96.5 },
  { period: "Jul 2026", csexValue: 74.0, cseyValue: 72.4, cohortMedian: 97.9, sectorBaseline: 96.4 },
  { period: "Aug 2026", csexValue: 69.0, cseyValue: 68.2, cohortMedian: 97.9, sectorBaseline: 96.5 },
  { period: "Sep 2026", csexValue: 68.8, cseyValue: 67.5, cohortMedian: 98.0, sectorBaseline: 96.6 },
];

export const telemetryCompletenessByAssetClass = [
  { assetClass: "Domain Controllers (AD)", csexPct: 100, cohortPct: 100, status: "compliant" },
  { assetClass: "Core Payment Switches", csexPct: 42.8, cohortPct: 99.4, status: "critical_gap" },
  { assetClass: "SWIFT Messaging Gateways", csexPct: 60.0, cohortPct: 100, status: "attention" },
  { assetClass: "SCADA / RTU Controllers", csexPct: 0, cohortPct: 97.8, status: "not_applicable" },
  { assetClass: "Database Servers (Oracle/PG)", csexPct: 88.2, cohortPct: 98.5, status: "attention" },
  { assetClass: "Perimeter Firewalls (NGFW)", csexPct: 98.5, cohortPct: 99.8, status: "compliant" },
  { assetClass: "Endpoint EDR Agents", csexPct: 94.1, cohortPct: 96.2, status: "compliant" },
];

export const riskDecompositionTrend = [
  { period: "Mar 2026", executionGap: 8.2, negativeSpace: 4.1, peerDeviation: 5.0, anomaly: 6.2, total: 23.5 },
  { period: "Apr 2026", executionGap: 11.4, negativeSpace: 5.2, peerDeviation: 7.1, anomaly: 6.5, total: 30.2 },
  { period: "May 2026", executionGap: 14.8, negativeSpace: 8.4, peerDeviation: 9.8, anomaly: 7.0, total: 40.0 },
  { period: "Jun 2026", executionGap: 18.2, negativeSpace: 12.1, peerDeviation: 12.4, anomaly: 7.8, total: 50.5 },
  { period: "Jul 2026", executionGap: 21.0, negativeSpace: 16.5, peerDeviation: 14.2, anomaly: 8.1, total: 59.8 },
  { period: "Aug 2026", executionGap: 23.5, negativeSpace: 19.6, peerDeviation: 15.7, anomaly: 8.4, total: 67.2 },
  { period: "Sep 2026", executionGap: 28.4, negativeSpace: 22.0, peerDeviation: 17.8, anomaly: 10.2, total: 78.4 },
];

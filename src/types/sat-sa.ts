export interface StatItem {
  value: string;
  label: string;
}

export interface AgentGroup {
  family: "MLOps" | "SAT-SA";
  count: number;
  description: string;
  agents: string[];
}

export interface DetectorGroup {
  title: string;
  items: string[];
}

export interface TrustCell {
  label: string;
  value: string;
  meta: string;
}

export interface RiskDimension {
  name: string;
}

export interface LimitationItem {
  title: string;
  detail: string;
}

export interface RepoTreeEntry {
  name: string;
  note: string;
}

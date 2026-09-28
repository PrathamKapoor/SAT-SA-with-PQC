import type { EvidenceCategory } from "@/lib/api/types";

/**
 * Mirror of satsa/ingest/spec.py CATEGORY_FIELDS: canonical field names,
 * accepted column aliases and requiredness. Used only for the browser-side
 * PRE-CHECK on the ingest screen; the backend's ingestion service is the
 * authoritative validator. Keep in sync with spec.py.
 */
export interface FieldSpec {
  name: string;
  aliases: string[];
  required: boolean;
}

const f = (name: string, aliases: string[], required = false): FieldSpec => ({ name, aliases, required });

export const CATEGORY_FIELDS: Record<EvidenceCategory, FieldSpec[]> = {
  alerts: [
    f("native_id", ["alert_id", "id", "AlertID"], true),
    f("created_at", ["timestamp", "time", "created", "raised_at"], true),
    f("severity", ["native_severity", "priority", "sev"]),
    f("category", ["native_category", "type", "alert_type"]),
    f("acknowledged_at", ["ack_at", "acknowledged"]),
    f("closed_at", ["resolved_at", "closed", "close_time"]),
    f("case_ids", ["case_id", "cases", "case"]),
    f("asset_ids", ["assets", "asset", "asset_id", "host", "hostname"]),
  ],
  cases: [
    f("native_id", ["case_id", "id", "CaseID"], true),
    f("opened_at", ["created_at", "opened", "timestamp"], true),
    f("status", []),
    f("closed_at", ["closed", "resolve_time"]),
    f("owner", ["owner_pseudonym", "analyst", "assignee"]),
    f("alert_ids", ["alerts", "alert_id", "alert"]),
    f("closure_reason", ["reason_notes", "closure_notes"]),
  ],
  investigation_steps: [
    f("case_id", ["case"], true),
    f("action_type", ["action", "step_type", "type"], true),
    f("performed_at", ["timestamp", "time", "performed"], true),
    f("sequence", ["seq", "order", "step_no"]),
    f("analyst", ["analyst_pseudonym", "analyst_id", "actor"]),
    f("note", ["note_text", "notes", "description", "details"]),
    f("evidence_ids", ["evidence", "evidence_refs"]),
  ],
  escalations: [
    f("alert_id", ["alert"]),
    f("case_id", ["case"]),
    f("occurred_at", ["timestamp", "time", "escalated_at"], true),
    f("destination_role", ["destination", "escalated_to", "to_role"]),
    f("trigger", ["reason", "trigger_reason"]),
    f("outcome", ["result"]),
  ],
  dispositions: [
    f("alert_id", ["alert"]),
    f("case_id", ["case"]),
    f("occurred_at", ["timestamp", "time", "decided_at"], true),
    f("outcome", ["category", "verdict", "classification"]),
    f("reason", ["justification", "notes"]),
    f("approver_role", ["approver"]),
  ],
  assets: [
    f("native_id", ["asset_id", "id", "hostname", "host"], true),
    f("criticality", ["criticality_level", "tier"]),
    f("environment", ["env", "zone"]),
    f("controls", ["control_applicability", "applicable_controls"]),
  ],
};

export type SourceFormat = "csv" | "json" | "jsonl" | "sqlite";

export function detectFormat(filename: string): SourceFormat | null {
  const ext = filename.toLowerCase().split(".").pop();
  if (ext === "csv") return "csv";
  if (ext === "json") return "json";
  if (ext === "jsonl" || ext === "ndjson") return "jsonl";
  if (ext === "db" || ext === "sqlite" || ext === "sqlite3") return "sqlite";
  return null;
}

/** Category from the filename base, as the backend's directory reader does (alerts.csv -> alerts). */
export function detectCategory(filename: string): EvidenceCategory | null {
  const base = filename.toLowerCase().replace(/\.[^.]+$/, "");
  const known: EvidenceCategory[] = ["alerts", "cases", "investigation_steps", "escalations", "dispositions", "assets"];
  return known.find((c) => base === c || base.endsWith(`_${c}`) || base.endsWith(`-${c}`)) ?? null;
}

export interface FieldMatch {
  field: FieldSpec;
  column: string | null;
}

export function matchColumns(category: EvidenceCategory, columns: string[]): FieldMatch[] {
  const lower = new Map(columns.map((c) => [c.trim().toLowerCase(), c.trim()]));
  return CATEGORY_FIELDS[category].map((field) => {
    const hit = [field.name, ...field.aliases].map((n) => lower.get(n.toLowerCase())).find(Boolean) ?? null;
    return { field, column: hit };
  });
}

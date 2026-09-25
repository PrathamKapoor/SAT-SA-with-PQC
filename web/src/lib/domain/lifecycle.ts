import type { AlertRecord, SecurityData } from "@/lib/types/domain";

/**
 * Operational lifecycle of an alert, reconstructed ONLY from submitted
 * records (alert timestamps, linked cases' investigation steps, escalation
 * and disposition records). A stage is "missing" when the submission holds
 * no record for it; the UI never infers that work happened.
 */
export type StageKey = "raised" | "acknowledged" | "investigated" | "escalated" | "dispositioned" | "closed";
export type StageState = "present" | "missing";

export interface LifecycleStage {
  key: StageKey;
  label: string;
  state: StageState;
  at: number | null;
  detail: string;
}

export interface AlertLifecycle {
  alert: AlertRecord;
  stages: LifecycleStage[];
  secondsToClose: number | null;
  investigationSteps: number;
}

export const STAGE_LABEL: Record<StageKey, string> = {
  raised: "Raised",
  acknowledged: "Acknowledged",
  investigated: "Investigated",
  escalated: "Escalated",
  dispositioned: "Disposition",
  closed: "Closed",
};

export function alertLifecycle(alert: AlertRecord, data: SecurityData): AlertLifecycle {
  const caseIds = new Set(alert.caseRefs);
  const steps = data.investigationSteps
    .filter((s) => caseIds.has(s.caseId))
    .sort((a, b) => a.performedAt - b.performedAt);
  const escalation = data.escalations
    .filter((e) => e.alertId === alert.id || (e.caseId && caseIds.has(e.caseId)))
    .sort((a, b) => a.occurredAt - b.occurredAt)[0];
  const disposition = data.dispositions
    .filter((d) => d.alertId === alert.id || d.id === alert.dispositionId)
    .sort((a, b) => a.occurredAt - b.occurredAt)[0];

  const stages: LifecycleStage[] = [
    { key: "raised", label: STAGE_LABEL.raised, state: "present", at: alert.createdAt, detail: `${alert.mappedSeverity} severity` },
    {
      key: "acknowledged",
      label: STAGE_LABEL.acknowledged,
      state: alert.acknowledgedAt ? "present" : "missing",
      at: alert.acknowledgedAt,
      detail: alert.acknowledgedAt ? "" : "No acknowledgement recorded",
    },
    {
      key: "investigated",
      label: STAGE_LABEL.investigated,
      state: steps.length ? "present" : "missing",
      at: steps[0]?.performedAt ?? null,
      detail: steps.length ? `${steps.length} step${steps.length === 1 ? "" : "s"}: ${[...new Set(steps.map((s) => s.actionType))].join(", ")}` : "No investigation step on linked cases",
    },
    {
      key: "escalated",
      label: STAGE_LABEL.escalated,
      state: escalation ? "present" : "missing",
      at: escalation?.occurredAt ?? null,
      detail: escalation ? `to ${escalation.destinationRole || "unspecified role"}` : "No escalation record",
    },
    {
      key: "dispositioned",
      label: STAGE_LABEL.dispositioned,
      state: disposition ? "present" : "missing",
      at: disposition?.occurredAt ?? null,
      detail: disposition ? disposition.mappedCategory.replaceAll("_", " ") : "No disposition record",
    },
    {
      key: "closed",
      label: STAGE_LABEL.closed,
      state: alert.closedAt ? "present" : "missing",
      at: alert.closedAt,
      detail: alert.closedAt ? "" : "Still open at submission",
    },
  ];

  return {
    alert,
    stages,
    secondsToClose: alert.closedAt ? alert.closedAt - alert.createdAt : null,
    investigationSteps: steps.length,
  };
}

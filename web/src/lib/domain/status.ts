import type { Tone } from "@/components/ui/badges";
import type { DecisionAction, RunStatus, VerificationStatus, VersionStatus } from "@/lib/api/types";

/**
 * Labels for the backend's status vocabularies (docs/API_CONTRACT.md,
 * section 7). Each field keeps its own vocabulary; nothing here derives a
 * state the backend did not report.
 */
export const RUN_STATUS: Record<RunStatus, { label: string; tone: Tone }> = {
  queued: { label: "Queued", tone: "neutral" },
  running: { label: "Running", tone: "info" },
  awaiting_review: { label: "Awaiting review", tone: "attention" },
  cancel_requested: { label: "Cancel requested", tone: "neutral" },
  cancelled: { label: "Cancelled", tone: "neutral" },
  completed: { label: "Completed", tone: "brand" },
  partial: { label: "Partial", tone: "attention" },
  failed: { label: "Failed", tone: "critical" },
};

/** Runs whose state the worker is still changing without a human action. */
export const RUN_IN_PROGRESS: RunStatus[] = ["queued", "running", "cancel_requested"];

export const VERSION_STATUS: Record<VersionStatus, { label: string; tone: Tone }> = {
  created: { label: "Created", tone: "neutral" },
  uploading: { label: "Uploading", tone: "info" },
  uploaded: { label: "Uploaded", tone: "info" },
  validating: { label: "Validating", tone: "info" },
  valid: { label: "Valid", tone: "brand" },
  invalid: { label: "Invalid", tone: "attention" },
  failed: { label: "Validation failed", tone: "critical" },
};

export const VERIFICATION_STATUS: Record<VerificationStatus, { label: string; tone: Tone; detail: string }> = {
  verified: { label: "Verified", tone: "brand", detail: "The signed supervisory record matches the rebuilt state and the ledger." },
  inconsistent: { label: "Inconsistent", tone: "critical", detail: "The recorded state does not match its signature or the ledger." },
  not_finalized: { label: "Not finalized", tone: "neutral", detail: "Trust finalization has not completed for this run." },
  unavailable: { label: "Unavailable", tone: "attention", detail: "A verification dependency was unavailable." },
};

export const DECISION_ACTION: Record<DecisionAction, { label: string; tone: Tone; help: string }> = {
  confirm: { label: "Confirm", tone: "brand", help: "The findings stand as a supervisory result for this assessment." },
  dismiss: { label: "Dismiss", tone: "neutral", help: "The findings do not warrant supervisory action." },
  escalate: { label: "Escalate", tone: "attention", help: "The findings need escalation beyond this review." },
};

export const STEP_STATUS: Record<string, Tone> = {
  pending: "neutral",
  running: "info",
  completed: "brand",
  failed: "critical",
  skipped: "neutral",
};

export const FINDING_STATE_LABEL: Record<string, string> = {
  signal: "Signal",
  no_signal: "No signal",
  insufficient_data: "Insufficient data",
  not_applicable: "Not applicable",
  error: "Error",
};

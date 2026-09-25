import type { BackendReviewAction } from "@/lib/types/domain";

/**
 * Supervisory review actions shown in the UI, mapped onto the actions the
 * backend ReviewService accepts today (confirm | dismiss | escalate |
 * request_review | annotate). Actions with `backend: null` have no backend
 * equivalent yet: they are displayed, disabled, and listed in
 * docs/API_CONTRACT.md as required backend work. Nothing is recorded for them.
 */
export type ReviewActionKey = "confirm" | "reject" | "defer" | "request_evidence" | "escalate" | "false_positive";

export interface ReviewActionDef {
  key: ReviewActionKey;
  label: string;
  backend: BackendReviewAction | null;
  hint: string;
  tone: "primary" | "neutral" | "attention";
}

export const REVIEW_ACTIONS: ReviewActionDef[] = [
  { key: "confirm", label: "Confirm", backend: "confirm", hint: "The finding is supported by the evidence", tone: "primary" },
  { key: "reject", label: "Reject", backend: "dismiss", hint: "Recorded as dismiss", tone: "neutral" },
  { key: "escalate", label: "Escalate", backend: "escalate", hint: "Refer for higher supervisory review", tone: "attention" },
  { key: "request_evidence", label: "Request evidence", backend: "request_review", hint: "Recorded as request_review", tone: "neutral" },
  { key: "defer", label: "Defer", backend: null, hint: "Needs backend support: no defer action exists yet", tone: "neutral" },
  { key: "false_positive", label: "False positive", backend: null, hint: "Needs backend support: no false-positive action exists yet", tone: "neutral" },
];

export type ReviewStatusKey = "awaiting" | "confirmed" | "rejected" | "escalated" | "evidence_requested" | "annotated";

export const STATUS_FOR_ACTION: Record<BackendReviewAction, ReviewStatusKey> = {
  confirm: "confirmed",
  dismiss: "rejected",
  escalate: "escalated",
  request_review: "evidence_requested",
  annotate: "annotated",
};

export const BACKEND_ACTION_LABEL: Record<BackendReviewAction, string> = {
  confirm: "Confirmed",
  dismiss: "Rejected",
  escalate: "Escalated",
  request_review: "Evidence requested",
  annotate: "Annotated",
};

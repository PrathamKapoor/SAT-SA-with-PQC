import { AlertTriangle, CircleDot, Minus, ShieldAlert, ShieldCheck, ShieldQuestion } from "lucide-react";
import type { ReactNode } from "react";
import { FAMILY_LABEL, SEVERITY_LABEL, type FindingFamily } from "@/lib/domain/labels";
import type { Severity } from "@/lib/types/domain";
import { cn } from "@/lib/utils";

export type Tone = "neutral" | "brand" | "info" | "attention" | "critical";

const TONE: Record<Tone, string> = {
  neutral: "border-line-2 bg-paper text-ink-2",
  brand: "border-brand/25 bg-brand-tint text-brand-strong",
  info: "border-info/25 bg-info-tint text-info",
  attention: "border-attention/30 bg-attention-tint text-attention-strong",
  critical: "border-critical/30 bg-critical-tint text-critical",
};

/** Compact, square-cornered tag. Deliberately not a pill. */
export function Tag({ tone = "neutral", icon, children, className }: { tone?: Tone; icon?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex h-5 items-center gap-1 rounded-xs border px-1.5 font-mono text-[10.5px] font-medium tracking-[0.04em] uppercase whitespace-nowrap",
        TONE[tone],
        className,
      )}
    >
      {icon}
      {children}
    </span>
  );
}

const SEVERITY_TONE: Record<Severity, Tone> = { high: "attention", medium: "info", low: "neutral" };

/**
 * Severity as the backend buckets it (satsa.analysis.prioritize._severity_of):
 * a coarse rule-family bucket, not an incident severity.
 */
export function SeverityMark({ severity, className }: { severity: Severity | null; className?: string }) {
  if (!severity) return <span className={cn("text-faint", className)}>n/a</span>;
  const bars = severity === "high" ? 3 : severity === "medium" ? 2 : 1;
  const color = severity === "high" ? "bg-attention" : severity === "medium" ? "bg-info" : "bg-faint";
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-[12.5px] text-ink-2", className)}>
      <span aria-hidden="true" className="flex h-3 items-end gap-[2px]">
        {[1, 2, 3].map((i) => (
          <span key={i} className={cn("w-[3px] rounded-[1px]", i <= bars ? color : "bg-line-2")} style={{ height: 4 + i * 3 }} />
        ))}
      </span>
      {SEVERITY_LABEL[severity]}
      <span className="sr-only"> severity</span>
    </span>
  );
}

export function SeverityTag({ severity }: { severity: Severity | null }) {
  if (!severity) return null;
  return (
    <Tag tone={SEVERITY_TONE[severity]} icon={severity === "high" ? <AlertTriangle className="size-3" aria-hidden="true" /> : undefined}>
      {SEVERITY_LABEL[severity]}
    </Tag>
  );
}

const FAMILY_DOT: Partial<Record<FindingFamily, string>> = {
  execution_gap: "bg-attention",
  negative_space: "bg-brand",
  anomaly: "bg-info",
  peer_benchmark: "bg-ink-2",
  coverage_gap: "bg-brand",
  evidence_completeness: "bg-faint",
  case_similarity: "bg-info",
};

export function FamilyLabel({ family, className }: { family: FindingFamily; className?: string }) {
  return (
    <span className={cn("label inline-flex items-center gap-1.5 text-ink-2", className)}>
      <span aria-hidden="true" className={cn("size-1.5 rounded-full", FAMILY_DOT[family] ?? "bg-faint")} />
      {FAMILY_LABEL[family]}
    </span>
  );
}

export type ReviewStatus = "awaiting" | "confirmed" | "rejected" | "escalated" | "evidence_requested" | "annotated";

const REVIEW_STATUS: Record<ReviewStatus, { label: string; tone: Tone }> = {
  awaiting: { label: "Awaiting review", tone: "neutral" },
  confirmed: { label: "Confirmed", tone: "brand" },
  rejected: { label: "Rejected", tone: "neutral" },
  escalated: { label: "Escalated", tone: "attention" },
  evidence_requested: { label: "Evidence requested", tone: "info" },
  annotated: { label: "Annotated", tone: "neutral" },
};

export function ReviewStatusTag({ status }: { status: ReviewStatus }) {
  const s = REVIEW_STATUS[status];
  return (
    <Tag tone={s.tone} icon={status === "awaiting" ? <CircleDot className="size-3" aria-hidden="true" /> : undefined}>
      {s.label}
    </Tag>
  );
}

export type TrustState = "verified" | "failed" | "unsigned" | "unknown";

const TRUST: Record<TrustState, { label: string; tone: Tone; icon: ReactNode }> = {
  verified: { label: "Verified", tone: "brand", icon: <ShieldCheck className="size-3" aria-hidden="true" /> },
  failed: { label: "Verification failed", tone: "critical", icon: <ShieldAlert className="size-3" aria-hidden="true" /> },
  unsigned: { label: "No receipt", tone: "attention", icon: <ShieldQuestion className="size-3" aria-hidden="true" /> },
  unknown: { label: "Not checked", tone: "neutral", icon: <Minus className="size-3" aria-hidden="true" /> },
};

export function TrustTag({ state, className }: { state: TrustState; className?: string }) {
  const t = TRUST[state];
  return (
    <Tag tone={t.tone} icon={t.icon} className={className}>
      {t.label}
    </Tag>
  );
}

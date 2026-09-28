import { ChevronRight, Paperclip } from "lucide-react";
import Link from "next/link";
import { FamilyLabel, Tag } from "@/components/ui/badges";
import { ConfidenceInline } from "@/components/ui/data";
import { EmptyState } from "@/components/ui/states";
import type { Finding } from "@/lib/api/types";
import { familyOf, ruleTitle } from "@/lib/domain/labels";
import { FINDING_STATE_LABEL } from "@/lib/domain/status";

/** Findings as the backend returned them: rule, state, confidence, cited evidence. `runEntityNames` maps run id to entity name. */
export function FindingList({ findings, runEntityNames, empty }: { findings: Finding[]; runEntityNames?: Map<string, string>; empty: string }) {
  if (!findings.length) return <EmptyState title={empty} />;
  return (
    <ul aria-label="Findings" className="overflow-hidden rounded-md border border-line bg-paper">
      {findings.map((f) => (
        <li key={f.id} className="border-b border-line last:border-0">
          <Link
            href={`/workbench/findings/${f.id}`}
            className="group grid grid-cols-1 gap-x-5 gap-y-2 px-4 py-3 hover:bg-canvas md:grid-cols-[minmax(0,1fr)_7rem_6.5rem_4rem_1rem] md:items-center"
          >
            <span className="min-w-0">
              <FamilyLabel family={familyOf(f.rule_or_category)} />
              <span className="mt-1 block truncate text-[14px] font-medium text-ink group-hover:text-brand-strong">{ruleTitle(f.rule_or_category)}</span>
              <span className="mt-0.5 block truncate font-mono text-[11.5px] text-muted">
                {f.rule_or_category}
                {runEntityNames?.get(f.run_id) ? ` · ${runEntityNames.get(f.run_id)}` : ""}
              </span>
            </span>
            <span>
              <Tag tone={f.state === "signal" ? "attention" : f.state === "error" ? "critical" : "neutral"}>{FINDING_STATE_LABEL[f.state] ?? f.state}</Tag>
            </span>
            <ConfidenceInline confidence={f.confidence} />
            <span className="inline-flex items-center gap-1 text-[12.5px] text-muted" title="Cited source records">
              <Paperclip className="size-3.5" aria-hidden="true" />
              <span className="num">{f.evidence_refs.length}</span>
              <span className="sr-only"> cited records</span>
            </span>
            <ChevronRight className="hidden size-4 text-faint group-hover:text-ink md:block" aria-hidden="true" />
          </Link>
        </li>
      ))}
    </ul>
  );
}

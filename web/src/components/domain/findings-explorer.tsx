"use client";

import { Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import { EmptyState } from "@/components/ui/states";
import { FAMILY_LABEL, ruleTitle, type FindingFamily } from "@/lib/domain/labels";
import { STATUS_FOR_ACTION } from "@/lib/domain/review";
import { useReviewStore } from "@/lib/review-store";
import type { Severity } from "@/lib/types/domain";
import { cn } from "@/lib/utils";
import { FindingRow, type FindingRowData } from "./finding-row";

function withDevStatus(f: FindingRowData, devAction?: keyof typeof STATUS_FOR_ACTION): FindingRowData {
  return devAction && f.reviewStatus === "awaiting" ? { ...f, reviewStatus: STATUS_FOR_ACTION[devAction] } : f;
}

type SortKey = "priority" | "confidence" | "evidence";
type StatusFilter = "all" | "awaiting" | "decided";

function Select<T extends string>({ label, value, onChange, options }: { label: string; value: T; onChange: (v: T) => void; options: Array<[T, string]> }) {
  return (
    <label className="flex items-center gap-2">
      <span className="label">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as T)}
        className="h-8 rounded-sm border border-line-2 bg-paper pr-7 pl-2 text-[13px] text-ink focus:border-brand focus:outline-none"
      >
        {options.map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>
    </label>
  );
}

export function FindingsExplorer({ findings, entities }: { findings: FindingRowData[]; entities: Array<{ id: string; name: string }> }) {
  const { decisions, latestFor } = useReviewStore();
  const devDecided = useMemo(() => new Set(decisions.map((d) => d.findingId)), [decisions]);
  const [family, setFamily] = useState<FindingFamily | "all">("all");
  const [entity, setEntity] = useState("all");
  const [severity, setSeverity] = useState<Severity | "all">("all");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [sort, setSort] = useState<SortKey>("priority");
  const [q, setQ] = useState("");

  const familyCounts = useMemo(() => {
    const m = new Map<FindingFamily, number>();
    for (const f of findings) m.set(f.family, (m.get(f.family) ?? 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [findings]);

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const out = findings.filter((f) => {
      const awaiting = f.reviewStatus === "awaiting" && !devDecided.has(f.id);
      return (
        (family === "all" || f.family === family) &&
        (entity === "all" || f.entityId === entity) &&
        (severity === "all" || f.severity === severity) &&
        (status === "all" || (status === "awaiting" ? awaiting : !awaiting)) &&
        (!needle || `${ruleTitle(f.ruleOrCategory)} ${f.ruleOrCategory} ${f.entityName} ${f.rationale}`.toLowerCase().includes(needle))
      );
    });
    const key: Record<SortKey, (f: FindingRowData) => number> = {
      priority: (f) => f.priorityScore ?? 0,
      confidence: (f) => f.confidence?.overall ?? 0,
      evidence: (f) => f.evidenceCount,
    };
    return out.sort((a, b) => key[sort](b) - key[sort](a));
  }, [findings, family, entity, severity, status, sort, q, devDecided]);

  const filtered = family !== "all" || entity !== "all" || severity !== "all" || status !== "all" || q;

  return (
    <div>
      <div role="tablist" aria-label="Finding family" className="-mx-1 flex gap-1 overflow-x-auto border-b border-line px-1">
        {[["all", findings.length] as const, ...familyCounts].map(([key, n]) => (
          <button
            key={key}
            role="tab"
            aria-selected={family === key}
            onClick={() => setFamily(key as FindingFamily | "all")}
            className={cn(
              "relative -mb-px flex h-10 shrink-0 items-center gap-1.5 border-b-2 px-2.5 text-[13px] whitespace-nowrap transition-colors",
              family === key ? "border-ink font-medium text-ink" : "border-transparent text-muted hover:text-ink",
            )}
          >
            {key === "all" ? "All families" : FAMILY_LABEL[key as FindingFamily]}
            <span className="num text-[11.5px] text-faint">{n}</span>
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-3 py-4">
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-faint" aria-hidden="true" />
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search findings"
            aria-label="Search findings"
            className="h-8 w-56 rounded-sm border border-line-2 bg-paper pr-2 pl-8 text-[13px] placeholder:text-faint focus:border-brand focus:outline-none"
          />
        </div>
        <Select label="Entity" value={entity} onChange={setEntity} options={[["all", "All"], ...entities.map((e) => [e.id, e.name] as [string, string])]} />
        <Select label="Severity" value={severity} onChange={setSeverity} options={[["all", "All"], ["high", "High"], ["medium", "Medium"], ["low", "Low"]]} />
        <Select label="Status" value={status} onChange={setStatus} options={[["all", "All"], ["awaiting", "Awaiting review"], ["decided", "Decided"]]} />
        <Select label="Sort" value={sort} onChange={setSort} options={[["priority", "Priority"], ["confidence", "Confidence"], ["evidence", "Evidence"]]} />
        {filtered && (
          <button
            type="button"
            onClick={() => {
              setFamily("all");
              setEntity("all");
              setSeverity("all");
              setStatus("all");
              setQ("");
            }}
            className="inline-flex items-center gap-1 text-[12.5px] text-muted hover:text-ink"
          >
            <X className="size-3.5" aria-hidden="true" />
            Clear
          </button>
        )}
        <p className="ml-auto text-[12.5px] text-muted" aria-live="polite">
          <span className="num font-medium text-ink">{rows.length}</span> of {findings.length}
        </p>
      </div>

      <div className="hidden grid-cols-[6.5rem_minmax(0,1fr)_7.5rem_5rem_9.5rem_1rem] gap-x-5 border-y border-line bg-canvas px-4 py-2 md:grid" aria-hidden="true">
        {["Severity", "Finding", "Confidence", "Evidence", "Status", ""].map((h) => (
          <span key={h} className="label">
            {h}
          </span>
        ))}
      </div>
      {rows.length ? (
        <ul aria-label="Findings" className="rounded-b-md border-b border-line bg-paper max-md:border-t">
          {rows.map((f) => (
            <FindingRow key={f.id} f={withDevStatus(f, latestFor(f.id)?.action)} />
          ))}
        </ul>
      ) : (
        <EmptyState title="No findings match these filters" className="mt-4">
          Clear a filter to see more of the queue.
        </EmptyState>
      )}
    </div>
  );
}

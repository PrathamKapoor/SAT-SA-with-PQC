"use client";

import { useMemo, useState } from "react";
import { DataTable, type Column } from "@/components/ui/data";
import { fmtDateTime, fmtDuration } from "@/lib/domain/format";
import { CATEGORY_LABEL } from "@/lib/domain/labels";
import type { EvidenceCategory, SecurityData } from "@/lib/types/domain";
import { cn } from "@/lib/utils";

type Row = Record<string, unknown> & { id: string; entityId?: string; caseId?: string };

export function SecurityDataBrowser({ data, entities }: { data: SecurityData; entities: Array<{ id: string; name: string }> }) {
  const [tab, setTab] = useState<EvidenceCategory>("alerts");
  const [entity, setEntity] = useState("all");
  const name = useMemo(() => new Map(entities.map((e) => [e.id, e.name])), [entities]);
  const caseEntity = useMemo(() => new Map(data.cases.map((c) => [c.id, c.entityId])), [data.cases]);
  const native = useMemo(() => {
    const m = new Map<string, string>();
    for (const a of data.alerts) m.set(a.id, a.nativeId);
    for (const c of data.cases) m.set(c.id, c.nativeId);
    for (const a of data.assets) m.set(a.id, a.nativeId);
    return m;
  }, [data]);
  const ent = (id?: string) => (id ? name.get(id) ?? "" : "");
  const ref = (id: string | null | undefined) => (id ? native.get(id) ?? id.slice(0, 10) : "none");

  const tables: Record<EvidenceCategory, { rows: Row[]; columns: Column<Row>[] }> = {
    alerts: {
      rows: data.alerts as unknown as Row[],
      columns: [
        { key: "n", header: "Alert", cell: (r) => <span className="font-mono font-medium text-ink">{String(r.nativeId)}</span> },
        { key: "e", header: "Entity", cell: (r) => ent(r.entityId) },
        { key: "s", header: "Severity", cell: (r) => <span className="capitalize">{String(r.mappedSeverity)}</span> },
        { key: "c", header: "Raised", cell: (r) => fmtDateTime(r.createdAt as number) },
        { key: "a", header: "To acknowledge", cell: (r) => (r.acknowledgedAt ? fmtDuration((r.acknowledgedAt as number) - (r.createdAt as number)) : <span className="text-attention-strong">none</span>) },
        { key: "x", header: "To close", cell: (r) => (r.closedAt ? fmtDuration((r.closedAt as number) - (r.createdAt as number)) : "open") },
        { key: "k", header: "Cases", cell: (r) => (r.caseRefs as string[]).map(ref).join(", ") || "none" },
      ],
    },
    cases: {
      rows: data.cases as unknown as Row[],
      columns: [
        { key: "n", header: "Case", cell: (r) => <span className="font-mono font-medium text-ink">{String(r.nativeId)}</span> },
        { key: "e", header: "Entity", cell: (r) => ent(r.entityId) },
        { key: "s", header: "Status", cell: (r) => String(r.status) },
        { key: "o", header: "Owner", cell: (r) => String(r.ownerPseudonym || "none") },
        { key: "a", header: "Alerts", cell: (r) => (r.alertRefs as string[]).map(ref).join(", ") || "none" },
        { key: "d", header: "Open for", cell: (r) => (r.closedAt ? fmtDuration((r.closedAt as number) - (r.openedAt as number)) : "open") },
        { key: "c", header: "Closure reason", cell: (r) => String(r.closureReason || "none") },
      ],
    },
    investigation_steps: {
      rows: data.investigationSteps.map((s) => ({ ...s, entityId: caseEntity.get(s.caseId) })) as unknown as Row[],
      columns: [
        { key: "c", header: "Case", cell: (r) => <span className="font-mono text-ink">{ref(r.caseId)}</span> },
        { key: "e", header: "Entity", cell: (r) => ent(r.entityId) },
        { key: "q", header: "Seq", align: "right", cell: (r) => <span className="num">{String(r.sequence)}</span> },
        { key: "a", header: "Action", cell: (r) => String(r.actionType) },
        { key: "p", header: "Analyst", cell: (r) => String(r.analystPseudonym || "none") },
        { key: "n", header: "Note", cell: (r) => String(r.noteText || "none") },
        { key: "t", header: "Performed", cell: (r) => fmtDateTime(r.performedAt as number) },
      ],
    },
    escalations: {
      rows: data.escalations as unknown as Row[],
      columns: [
        { key: "a", header: "Alert", cell: (r) => <span className="font-mono text-ink">{ref(r.alertId as string)}</span> },
        { key: "c", header: "Case", cell: (r) => ref(r.caseId as string) },
        { key: "e", header: "Entity", cell: (r) => ent(r.entityId) },
        { key: "d", header: "To role", cell: (r) => String(r.destinationRole || "none") },
        { key: "t", header: "Trigger", cell: (r) => String(r.trigger || "none") },
        { key: "o", header: "Outcome", cell: (r) => String(r.outcome || "none") },
      ],
    },
    dispositions: {
      rows: data.dispositions as unknown as Row[],
      columns: [
        { key: "a", header: "Alert", cell: (r) => <span className="font-mono text-ink">{ref(r.alertId as string)}</span> },
        { key: "e", header: "Entity", cell: (r) => ent(r.entityId) },
        { key: "c", header: "Category", cell: (r) => String(r.mappedCategory).replaceAll("_", " ") },
        { key: "r", header: "Reason", cell: (r) => String(r.reason || "none") },
        { key: "p", header: "Approver", cell: (r) => String(r.approverRole || "none") },
      ],
    },
    assets: {
      rows: data.assets as unknown as Row[],
      columns: [
        { key: "n", header: "Asset", cell: (r) => <span className="font-mono font-medium text-ink">{String(r.nativeId)}</span> },
        { key: "e", header: "Entity", cell: (r) => ent(r.entityId) },
        { key: "c", header: "Criticality", cell: (r) => <span className="capitalize">{String(r.criticality)}</span> },
        { key: "v", header: "Environment", cell: (r) => String(r.environment || "none") },
        { key: "k", header: "Controls", cell: (r) => (r.controls as string[]).join(", ") || "none" },
      ],
    },
  };

  const t = tables[tab];
  const rows = entity === "all" ? t.rows : t.rows.filter((r) => r.entityId === entity);

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line">
        <div role="tablist" aria-label="Evidence category" className="-mb-px flex gap-1 overflow-x-auto">
          {(Object.keys(tables) as EvidenceCategory[]).map((k) => (
            <button
              key={k}
              role="tab"
              aria-selected={tab === k}
              onClick={() => setTab(k)}
              className={cn("h-10 shrink-0 border-b-2 px-2.5 text-[13px] whitespace-nowrap", tab === k ? "border-ink font-medium text-ink" : "border-transparent text-muted hover:text-ink")}
            >
              {CATEGORY_LABEL[k]} <span className="num text-[11.5px] text-faint">{tables[k].rows.length}</span>
            </button>
          ))}
        </div>
        <label className="mb-2 flex items-center gap-2">
          <span className="label">Entity</span>
          <select value={entity} onChange={(e) => setEntity(e.target.value)} className="h-8 rounded-sm border border-line-2 bg-paper px-2 text-[13px]">
            <option value="all">All</option>
            {entities.map((e) => (
              <option key={e.id} value={e.id}>
                {e.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div role="tabpanel" className="mt-2 rounded-md border border-line bg-paper px-5 py-2">
        <DataTable caption={`${CATEGORY_LABEL[tab]} records`} rows={rows} rowKey={(r) => r.id} columns={t.columns} dense empty={<p className="py-6 text-[13px] text-muted">No records for this filter.</p>} />
      </div>
    </div>
  );
}

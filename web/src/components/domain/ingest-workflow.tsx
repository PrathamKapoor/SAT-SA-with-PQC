"use client";

import { AlertTriangle, Check, CircleSlash, FileUp, FlaskConical, Info, Loader2, X } from "lucide-react";
import Link from "next/link";
import { useId, useRef, useState } from "react";
import { Tag } from "@/components/ui/badges";
import { Button, buttonClass } from "@/components/ui/button";
import { CATEGORY_LABEL } from "@/lib/domain/labels";
import { detectCategory, detectFormat, matchColumns, type FieldMatch, type SourceFormat } from "@/lib/domain/ingest-spec";
import { submitIngestion, type IngestOutcome } from "@/lib/ingest-actions";
import { EVIDENCE_CATEGORIES, type EvidenceCategory } from "@/lib/types/domain";
import { cn } from "@/lib/utils";

interface PrecheckedFile {
  file: File;
  format: SourceFormat | null;
  category: EvidenceCategory | null;
  records: number | null;
  columns: string[];
  matches: FieldMatch[];
  problems: string[];
}

const STEPS = ["Source", "Files", "Pre-check", "Submit", "Submission created", "Analysis ready"] as const;

async function precheck(file: File): Promise<PrecheckedFile> {
  const format = detectFormat(file.name);
  const category = detectCategory(file.name);
  const problems: string[] = [];
  let records: number | null = null;
  let columns: string[] = [];

  if (!format) problems.push("Unsupported format. Use CSV, JSON, JSONL or SQLite.");
  if (!category && format !== "sqlite") problems.push("Category not recognised from the filename (for example alerts.csv).");

  if (format === "csv" || format === "json" || format === "jsonl") {
    const text = await file.text();
    try {
      if (format === "csv") {
        const lines = text.split(/\r?\n/).filter((l) => l.trim());
        columns = (lines[0] ?? "").split(",").map((c) => c.replace(/^"|"$/g, "").trim());
        records = Math.max(0, lines.length - 1);
      } else if (format === "jsonl") {
        const rows = text.split(/\r?\n/).filter((l) => l.trim()).map((l) => JSON.parse(l) as Record<string, unknown>);
        records = rows.length;
        columns = [...new Set(rows.flatMap((r) => Object.keys(r)))];
      } else {
        const parsed = JSON.parse(text) as unknown;
        const rows = (Array.isArray(parsed) ? parsed : ((parsed as Record<string, unknown>)?.records as unknown[]) ?? []) as Record<string, unknown>[];
        records = rows.length;
        columns = [...new Set(rows.flatMap((r) => Object.keys(r ?? {})))];
      }
    } catch {
      problems.push("The file could not be parsed.");
    }
  }

  const matches = category && columns.length ? matchColumns(category, columns) : [];
  for (const m of matches) if (m.field.required && !m.column) problems.push(`Required field ${m.field.name} has no matching column.`);
  if (records === 0) problems.push("No records.");
  return { file, format, category, records, columns, matches, problems };
}

function Stepper({ current }: { current: number }) {
  return (
    <ol aria-label="Ingestion steps" className="flex flex-wrap items-center gap-y-2">
      {STEPS.map((s, i) => (
        <li key={s} className="flex items-center" aria-current={i === current ? "step" : undefined}>
          {i > 0 && <span aria-hidden="true" className={cn("mx-2 h-px w-6", i <= current ? "bg-ink" : "bg-line-2")} />}
          <span
            className={cn(
              "flex items-center gap-1.5 text-[12.5px]",
              i < current ? "text-ink" : i === current ? "font-semibold text-ink" : "text-faint",
            )}
          >
            <span
              aria-hidden="true"
              className={cn(
                "flex size-5 items-center justify-center rounded-full border font-mono text-[10.5px]",
                i < current ? "border-ink bg-ink text-white" : i === current ? "border-ink text-ink" : "border-line-2",
              )}
            >
              {i < current ? <Check className="size-3" strokeWidth={3} /> : i + 1}
            </span>
            {s}
          </span>
        </li>
      ))}
    </ol>
  );
}

function Field({ id, label, children, hint }: { id: string; label: string; children: React.ReactNode; hint?: string }) {
  return (
    <div>
      <label htmlFor={id} className="block text-[12.5px] font-medium text-ink">
        {label}
      </label>
      <div className="mt-1.5">{children}</div>
      {hint && <p className="mt-1 text-[11.5px] text-muted">{hint}</p>}
    </div>
  );
}

const input =
  "h-9 w-full rounded-sm border border-line-2 bg-paper px-2.5 text-[13px] text-ink placeholder:text-faint focus:border-brand focus:ring-2 focus:ring-brand/15 focus:outline-none";

export function IngestWorkflow({ mode, entities }: { mode: "fixture" | "api"; entities: string[] }) {
  const ids = { entity: useId(), sector: useId(), env: useId(), start: useId(), end: useId(), source: useId() };
  const fileInput = useRef<HTMLInputElement>(null);
  const [meta, setMeta] = useState({ entity: "", sector: "", environment: "", periodStart: "", periodEnd: "", sourceSystem: "" });
  const [files, setFiles] = useState<PrecheckedFile[]>([]);
  const [checking, setChecking] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [outcome, setOutcome] = useState<IngestOutcome | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const metaOk = meta.entity.trim() && meta.periodStart && meta.periodEnd && meta.periodStart <= meta.periodEnd;
  const blocking = files.some((f) => f.problems.length);
  const current = outcome?.ok ? (outcome.runId ? 5 : 4) : !metaOk ? 0 : !files.length ? 1 : 2;
  const covered = new Set(files.map((f) => f.category).filter(Boolean));

  const add = async (list: FileList | null) => {
    if (!list?.length) return;
    setChecking(true);
    const checked = await Promise.all([...list].map(precheck));
    setFiles((prev) => [...prev.filter((p) => !checked.some((c) => c.file.name === p.file.name)), ...checked]);
    setChecking(false);
    setOutcome(null);
  };

  const submit = async () => {
    setSubmitting(true);
    const form = new FormData();
    Object.entries(meta).forEach(([k, v]) => form.set(k, v));
    files.forEach((f) => form.append(f.category ?? "sqlite", f.file, f.file.name));
    setOutcome(await submitIngestion(form));
    setSubmitting(false);
  };

  return (
    <div className="space-y-6">
      <div className="rounded-md border border-line bg-paper px-5 py-4">
        <Stepper current={current} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[22rem_minmax(0,1fr)]">
        <section aria-labelledby="src-h" className="rounded-md border border-line bg-paper px-5 py-5">
          <h2 id="src-h" className="mb-4 flex items-center gap-2 text-[14px] font-semibold text-ink">
            <span className="label text-faint">01</span> Source
          </h2>
          <div className="space-y-4">
            <Field id={ids.entity} label="Entity" hint="An existing entity name, or a new one to register.">
              <input id={ids.entity} list={`${ids.entity}-list`} className={input} value={meta.entity} onChange={(e) => setMeta({ ...meta, entity: e.target.value })} placeholder="CSE-X" required />
              <datalist id={`${ids.entity}-list`}>
                {entities.map((e) => (
                  <option key={e} value={e} />
                ))}
              </datalist>
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field id={ids.sector} label="Sector">
                <input id={ids.sector} className={input} value={meta.sector} onChange={(e) => setMeta({ ...meta, sector: e.target.value })} placeholder="defence" />
              </Field>
              <Field id={ids.env} label="Environment">
                <input id={ids.env} className={input} value={meta.environment} onChange={(e) => setMeta({ ...meta, environment: e.target.value })} placeholder="on-prem" />
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field id={ids.start} label="Period start">
                <input id={ids.start} type="date" className={input} value={meta.periodStart} onChange={(e) => setMeta({ ...meta, periodStart: e.target.value })} required />
              </Field>
              <Field id={ids.end} label="Period end">
                <input id={ids.end} type="date" className={input} value={meta.periodEnd} onChange={(e) => setMeta({ ...meta, periodEnd: e.target.value })} required />
              </Field>
            </div>
            {meta.periodStart && meta.periodEnd && meta.periodStart > meta.periodEnd && (
              <p role="alert" className="text-[12px] text-critical">
                The period must end after it starts.
              </p>
            )}
            <Field id={ids.source} label="Source system" hint="Recorded as provenance on the submission.">
              <input id={ids.source} className={input} value={meta.sourceSystem} onChange={(e) => setMeta({ ...meta, sourceSystem: e.target.value })} placeholder="SOC export, March cycle" />
            </Field>
          </div>
        </section>

        <div className="min-w-0 space-y-6">
          <section aria-labelledby="files-h" className="rounded-md border border-line bg-paper px-5 py-5">
            <h2 id="files-h" className="mb-4 flex items-center gap-2 text-[14px] font-semibold text-ink">
              <span className="label text-faint">02</span> Files
            </h2>
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                void add(e.dataTransfer.files);
              }}
              className={cn(
                "flex flex-col items-center justify-center gap-2 rounded-md border border-dashed px-6 py-8 text-center transition-colors",
                dragging ? "border-brand bg-brand-tint/60" : "border-line-2 bg-canvas/60",
              )}
            >
              <FileUp className="size-5 text-muted" aria-hidden="true" />
              <p className="text-[13.5px] text-ink">
                Drop submission files, or{" "}
                <button type="button" onClick={() => fileInput.current?.click()} className="font-medium text-brand underline-offset-4 hover:underline">
                  choose files
                </button>
              </p>
              <p className="text-[12px] text-muted">CSV, JSON, JSONL or SQLite. One file per category, named after it (alerts.csv, cases.json).</p>
              <input ref={fileInput} type="file" multiple accept=".csv,.json,.jsonl,.ndjson,.db,.sqlite,.sqlite3" className="sr-only" onChange={(e) => void add(e.target.files)} aria-label="Submission files" />
            </div>
            <ul aria-label="Evidence categories covered" className="mt-4 flex flex-wrap gap-1.5">
              {EVIDENCE_CATEGORIES.map((c) => (
                <li key={c}>
                  <Tag tone={covered.has(c) ? "brand" : "neutral"} icon={covered.has(c) ? <Check className="size-3" aria-hidden="true" /> : undefined}>
                    {CATEGORY_LABEL[c]}
                  </Tag>
                </li>
              ))}
            </ul>
          </section>

          <section aria-labelledby="pre-h" aria-busy={checking} className="rounded-md border border-line bg-paper px-5 py-5">
            <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
              <h2 id="pre-h" className="flex items-center gap-2 text-[14px] font-semibold text-ink">
                <span className="label text-faint">03</span> Pre-check and field mapping
              </h2>
              <p className="text-[12px] text-muted">Runs in this browser against the SAT-SA field specification. The backend validates authoritatively.</p>
            </div>
            {checking && (
              <p role="status" className="flex items-center gap-2 text-[13px] text-muted">
                <Loader2 className="size-4 animate-spin" aria-hidden="true" /> Reading files
              </p>
            )}
            {!files.length && !checking && <p className="text-[13px] text-muted">Add files to see detected categories, record counts and column mapping.</p>}
            <ul className="space-y-4">
              {files.map((f) => (
                <li key={f.file.name} className="rounded-sm border border-line">
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-line bg-canvas px-3 py-2">
                    <span className="font-mono text-[12.5px] font-medium text-ink">{f.file.name}</span>
                    <span className="text-[12px] text-muted">
                      {f.format?.toUpperCase() ?? "Unknown"} · {f.category ? CATEGORY_LABEL[f.category] : "no category"} · {f.records ?? "n/a"} records · {(f.file.size / 1024).toFixed(1)} KB
                    </span>
                    <span className="ml-auto flex items-center gap-2">
                      {f.problems.length ? (
                        <Tag tone="critical" icon={<AlertTriangle className="size-3" aria-hidden="true" />}>
                          {f.problems.length} issue{f.problems.length === 1 ? "" : "s"}
                        </Tag>
                      ) : (
                        <Tag tone="brand" icon={<Check className="size-3" aria-hidden="true" />}>
                          Pre-check passed
                        </Tag>
                      )}
                      <button type="button" onClick={() => setFiles(files.filter((x) => x !== f))} aria-label={`Remove ${f.file.name}`} className="rounded-sm p-1 text-muted hover:bg-sunken hover:text-ink">
                        <X className="size-3.5" aria-hidden="true" />
                      </button>
                    </span>
                  </div>
                  {f.problems.length > 0 && (
                    <ul className="border-b border-line px-3 py-2 text-[12.5px] text-critical">
                      {f.problems.map((p) => (
                        <li key={p}>{p}</li>
                      ))}
                    </ul>
                  )}
                  {f.matches.length > 0 && (
                    <table className="w-full text-left text-[12.5px]">
                      <caption className="sr-only">Field mapping for {f.file.name}</caption>
                      <thead>
                        <tr>
                          <th scope="col" className="label px-3 pt-2 pb-1 font-normal">
                            SAT-SA field
                          </th>
                          <th scope="col" className="label px-3 pt-2 pb-1 font-normal">
                            Column in file
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {f.matches.map((m) => (
                          <tr key={m.field.name} className="border-t border-line/60">
                            <td className="px-3 py-1.5 font-mono text-ink">
                              {m.field.name}
                              {m.field.required && <span className="ml-1 text-muted">required</span>}
                            </td>
                            <td className={cn("px-3 py-1.5", m.column ? "text-ink-2" : m.field.required ? "font-medium text-critical" : "text-faint")}>
                              {m.column ?? (m.field.required ? "Missing" : "Not present")}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                  {f.format === "sqlite" && <p className="px-3 py-2 text-[12.5px] text-muted">SQLite tables are read and mapped by the backend adapter; the browser cannot inspect them.</p>}
                </li>
              ))}
            </ul>
          </section>

          <section aria-labelledby="sub-h" className="rounded-md border border-line bg-paper px-5 py-5">
            <h2 id="sub-h" className="mb-3 flex items-center gap-2 text-[14px] font-semibold text-ink">
              <span className="label text-faint">04</span> Submit
            </h2>
            <dl className="mb-4 grid grid-cols-2 gap-x-6 gap-y-2 text-[12.5px] sm:grid-cols-4">
              <div>
                <dt className="label">Files</dt>
                <dd className="num text-ink">{files.length}</dd>
              </div>
              <div>
                <dt className="label">Records (pre-check)</dt>
                <dd className="num text-ink">{files.reduce((n, f) => n + (f.records ?? 0), 0)}</dd>
              </div>
              <div>
                <dt className="label">Categories</dt>
                <dd className="num text-ink">{covered.size} of 6</dd>
              </div>
              <div>
                <dt className="label">Checksum</dt>
                <dd className="text-muted">SHA3-256 per file, computed on ingest</dd>
              </div>
            </dl>
            {mode === "fixture" ? (
              <p className="flex items-start gap-2 rounded-sm bg-attention-tint px-3 py-2.5 text-[12.5px] leading-relaxed text-attention-strong">
                <FlaskConical className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                No backend is connected, so nothing can be ingested. The pre-check above ran locally and no file left this browser.
              </p>
            ) : (
              <Button variant="primary" disabled={!metaOk || !files.length || blocking || submitting} onClick={submit}>
                {submitting && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
                {submitting ? "Ingesting" : "Ingest submission"}
              </Button>
            )}
            {covered.size > 0 && covered.size < 6 && (
              <p className="mt-3 flex items-start gap-1.5 text-[12px] text-muted">
                <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                Missing categories are allowed, but the evidence completeness worker will raise a finding for them.
              </p>
            )}
          </section>

          {outcome && (
            <section aria-live="polite" className={cn("rounded-md border px-5 py-5", outcome.ok ? "border-line bg-paper" : "border-critical/30 bg-critical-tint")}>
              {outcome.ok ? (
                <>
                  <h2 className="flex items-center gap-2 text-[14px] font-semibold text-ink">
                    <Check className="size-4 text-brand" aria-hidden="true" /> Submission created
                  </h2>
                  <p className="mt-1 font-mono text-[12px] text-muted">{outcome.submissionId}</p>
                  {outcome.entityId && (
                    <Link href={`/workbench/entities/${outcome.entityId}`} className={buttonClass("secondary", "sm", "mt-3")}>
                      Open entity
                    </Link>
                  )}
                </>
              ) : (
                <p className="flex items-center gap-2 text-[13px] text-critical">
                  <CircleSlash className="size-4" aria-hidden="true" />
                  {outcome.error}
                </p>
              )}
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

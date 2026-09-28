"use client";

import { AlertTriangle, Check, CircleDot, FileUp, Loader2, Play, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useRef, useState } from "react";
import { ActionError } from "@/components/ui/api-state";
import { Tag } from "@/components/ui/badges";
import { Button } from "@/components/ui/button";
import type { ApiErrorInfo } from "@/lib/api/errors";
import { EVIDENCE_CATEGORIES, type Assessment, type Entity, type EvidenceCategory, type Validation, type Version } from "@/lib/api/types";
import { fmtPeriod } from "@/lib/domain/format";
import { detectFormat, matchColumns } from "@/lib/domain/ingest-spec";
import { CATEGORY_LABEL } from "@/lib/domain/labels";
import {
  completeVersionAction,
  createAssessmentAction,
  createEntityAction,
  createSubmissionAction,
  createVersionAction,
  startRunAction,
  uploadArtifactAction,
  validateVersionAction,
} from "@/lib/workbench/actions";
import { cn } from "@/lib/utils";

const input =
  "h-9 w-full rounded-sm border border-line-2 bg-paper px-3 text-[13.5px] text-ink focus:border-brand focus:ring-2 focus:ring-brand/20 focus:outline-none";

type StepKey = "entity" | "assessment" | "submission" | "version" | "upload" | "complete" | "validate";
const STEP_LABEL: Record<StepKey, string> = {
  entity: "Register entity",
  assessment: "Open assessment period",
  submission: "Create submission",
  version: "Create submission version",
  upload: "Upload evidence files",
  complete: "Close the upload",
  validate: "Validate records",
};
type StepState = "pending" | "running" | "done" | "failed";

interface Precheck {
  problems: string[];
  records: number | null;
}

/** Browser pre-check of one file against satsa/ingest/spec.py. Advisory only: the backend validates. */
async function precheck(file: File, category: EvidenceCategory): Promise<Precheck> {
  const format = detectFormat(file.name);
  const problems: string[] = [];
  if (!format) return { problems: ["Unsupported format. Use CSV, JSON, JSONL or SQLite."], records: null };
  if (format === "sqlite") return { problems, records: null };
  let columns: string[] = [];
  let records: number | null = null;
  try {
    const text = await file.text();
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
    return { problems: ["The file could not be parsed."], records: null };
  }
  for (const m of matchColumns(category, columns)) if (m.field.required && !m.column) problems.push(`Required field ${m.field.name} has no matching column.`);
  if (records === 0) problems.push("No records.");
  return { problems, records };
}

function newKey(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

const toEpoch = (date: string, endOfDay = false) => {
  const t = Date.parse(`${date}T${endOfDay ? "23:59:59" : "00:00:00"}Z`);
  return Number.isFinite(t) ? t / 1000 : null;
};

export function IngestWorkflow({ entities, assessments, initialEntity }: { entities: Entity[]; assessments: Assessment[]; initialEntity?: string }) {
  const router = useRouter();
  const [entityMode, setEntityMode] = useState<"existing" | "new">(entities.length ? "existing" : "new");
  const [entityId, setEntityId] = useState(initialEntity && entities.some((e) => e.id === initialEntity) ? initialEntity : (entities[0]?.id ?? ""));
  const [newEntity, setNewEntity] = useState({ display_name: "", sector: "", environment_class: "" });
  const openAssessments = useMemo(() => assessments.filter((a) => a.entity_id === entityId && a.status === "open"), [assessments, entityId]);
  const firstOpen = (id: string) => assessments.find((a) => a.entity_id === id && a.status === "open")?.id ?? "new";
  const [assessmentId, setAssessmentId] = useState<string>(() => (entities.length ? firstOpen(entityId) : "new"));
  const [period, setPeriod] = useState({ start: "", end: "" });
  const [files, setFiles] = useState<Partial<Record<EvidenceCategory, File>>>({});
  const [checks, setChecks] = useState<Partial<Record<EvidenceCategory, Precheck>>>({});
  const [steps, setSteps] = useState<Partial<Record<StepKey, StepState>>>({});
  const [error, setError] = useState<{ step: StepKey | "run"; info: ApiErrorInfo } | null>(null);
  const [validation, setValidation] = useState<Validation | null>(null);
  const [version, setVersion] = useState<Version | null>(null);
  const [mode, setMode] = useState<"graph" | "standard">("graph");
  const [busy, setBusy] = useState(false);
  // Idempotency keys per logical step, reused when a failed sequence is retried.
  const keys = useRef<Record<string, string>>({});
  const created = useRef<{ entityId?: string; assessmentId?: string; submissionId?: string; versionId?: string; uploaded: Set<string> }>({ uploaded: new Set() });
  const keyFor = (name: string) => (keys.current[name] ??= newKey());

  const choose = async (category: EvidenceCategory, file: File | null) => {
    setFiles((f) => ({ ...f, [category]: file ?? undefined }));
    setChecks((c) => ({ ...c, [category]: undefined }));
    if (file) {
      const result = await precheck(file, category);
      setChecks((c) => ({ ...c, [category]: result }));
    }
  };

  const chosen = EVIDENCE_CATEGORIES.filter((c) => files[c]);
  const periodValid = assessmentId !== "new" || (toEpoch(period.start) !== null && toEpoch(period.end, true) !== null && period.start <= period.end);
  const entityValid = entityMode === "existing" ? Boolean(entityId) : Boolean(newEntity.display_name.trim());
  const ready = entityValid && periodValid && chosen.length > 0 && !busy && !validation;

  const mark = (step: StepKey, state: StepState) => setSteps((s) => ({ ...s, [step]: state }));

  async function runStep<T>(step: StepKey, call: () => Promise<{ ok: true; data: T } | { ok: false; error: ApiErrorInfo }>): Promise<T | null> {
    mark(step, "running");
    const r = await call();
    if (!r.ok) {
      mark(step, "failed");
      setError({ step, info: r.error });
      return null;
    }
    mark(step, "done");
    return r.data;
  }

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const c = created.current;
      if (!c.entityId) {
        if (entityMode === "existing") c.entityId = entityId;
        else {
          const e = await runStep("entity", () =>
            createEntityAction({ display_name: newEntity.display_name.trim(), sector: newEntity.sector.trim(), environment_class: newEntity.environment_class.trim() }),
          );
          if (!e) return;
          c.entityId = e.id;
        }
      }
      if (!c.assessmentId) {
        if (assessmentId !== "new") c.assessmentId = assessmentId;
        else {
          const a = await runStep("assessment", () =>
            createAssessmentAction({ entity_id: c.entityId!, period_start: toEpoch(period.start)!, period_end: toEpoch(period.end, true)! }),
          );
          if (!a) return;
          c.assessmentId = a.id;
        }
      }
      if (!c.submissionId) {
        const s = await runStep("submission", () => createSubmissionAction(c.assessmentId!, keyFor(`submission:${c.assessmentId}`)));
        if (!s) return;
        c.submissionId = s.id;
      }
      if (!c.versionId) {
        const v = await runStep("version", () => createVersionAction(c.submissionId!, keyFor(`version:${c.submissionId}`)));
        if (!v) return;
        c.versionId = v.id;
      }
      mark("upload", "running");
      for (const category of chosen) {
        const file = files[category]!;
        const id = `${category}:${file.name}:${file.size}:${file.lastModified}`;
        if (c.uploaded.has(id)) continue;
        const form = new FormData();
        form.append("version_id", c.versionId!);
        form.append("category", category);
        form.append("key", keyFor(`artifact:${c.versionId}:${id}`));
        form.append("file", file, file.name);
        const r = await uploadArtifactAction(form);
        if (!r.ok) {
          mark("upload", "failed");
          setError({ step: "upload", info: { ...r.error, message: `${CATEGORY_LABEL[category]}: ${r.error.message}` } });
          return;
        }
        c.uploaded.add(id);
      }
      mark("upload", "done");
      const completed = await runStep("complete", () => completeVersionAction(c.versionId!));
      if (!completed) return;
      const report = await runStep("validate", () => validateVersionAction(c.versionId!));
      if (!report) return;
      setVersion(completed);
      setValidation(report);
    } finally {
      setBusy(false);
    }
  };

  const start = async () => {
    if (!created.current.versionId) return;
    setBusy(true);
    setError(null);
    const r = await startRunAction(created.current.versionId, mode, keyFor(`run:${created.current.versionId}`));
    if (!r.ok) {
      setError({ step: "run", info: r.error });
      setBusy(false);
      return;
    }
    router.push(`/workbench/runs/${r.data.id}`);
  };

  const sequence: StepKey[] = [
    ...(entityMode === "new" ? (["entity"] as StepKey[]) : []),
    ...(assessmentId === "new" ? (["assessment"] as StepKey[]) : []),
    "submission",
    "version",
    "upload",
    "complete",
    "validate",
  ];

  return (
    <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_22rem]">
      <div className="space-y-8">
        <section aria-labelledby="entity-h">
          <h2 id="entity-h" className="mb-3 text-[15px] font-semibold text-ink">
            1. Entity
          </h2>
          <div className="mb-3 flex gap-2" role="radiogroup" aria-label="Entity source">
            {entities.length > 0 && (
              <Button
                size="sm"
                variant={entityMode === "existing" ? "primary" : "secondary"}
                onClick={() => {
                  setEntityMode("existing");
                  setAssessmentId(firstOpen(entityId));
                }} disabled={busy || Boolean(validation)} aria-pressed={entityMode === "existing"}>
                Existing entity
              </Button>
            )}
            <Button
              size="sm"
              variant={entityMode === "new" ? "primary" : "secondary"}
              onClick={() => {
                setEntityMode("new");
                setAssessmentId("new");
              }} disabled={busy || Boolean(validation)} aria-pressed={entityMode === "new"}>
              New entity
            </Button>
          </div>
          {entityMode === "existing" ? (
            <label className="block max-w-md">
              <span className="label mb-1 block">Entity</span>
              <select
                className={input}
                value={entityId}
                disabled={busy || Boolean(validation)}
                onChange={(e) => {
                  setEntityId(e.target.value);
                  setAssessmentId(firstOpen(e.target.value));
                }}
              >
                {entities.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.display_name}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <div className="grid max-w-2xl gap-3 sm:grid-cols-3">
              <label className="block sm:col-span-3">
                <span className="label mb-1 block">Display name</span>
                <input className={input} name="display_name" value={newEntity.display_name} maxLength={200} disabled={busy || Boolean(validation)} onChange={(e) => setNewEntity({ ...newEntity, display_name: e.target.value })} />
              </label>
              <label className="block">
                <span className="label mb-1 block">Sector</span>
                <input className={input} name="sector" value={newEntity.sector} maxLength={100} disabled={busy || Boolean(validation)} onChange={(e) => setNewEntity({ ...newEntity, sector: e.target.value })} />
              </label>
              <label className="block sm:col-span-2">
                <span className="label mb-1 block">Environment class</span>
                <input className={input} name="environment_class" value={newEntity.environment_class} maxLength={100} disabled={busy || Boolean(validation)} onChange={(e) => setNewEntity({ ...newEntity, environment_class: e.target.value })} />
              </label>
            </div>
          )}
        </section>

        <section aria-labelledby="period-h">
          <h2 id="period-h" className="mb-3 text-[15px] font-semibold text-ink">
            2. Assessment period
          </h2>
          {entityMode === "existing" && openAssessments.length > 0 && (
            <label className="mb-3 block max-w-md">
              <span className="label mb-1 block">Period</span>
              <select className={input} value={assessmentId} disabled={busy || Boolean(validation)} onChange={(e) => setAssessmentId(e.target.value)}>
                {openAssessments.map((a) => (
                  <option key={a.id} value={a.id}>
                    {fmtPeriod(a.period_start, a.period_end)}
                  </option>
                ))}
                <option value="new">New period</option>
              </select>
            </label>
          )}
          {assessmentId === "new" && (
            <div className="grid max-w-md grid-cols-2 gap-3">
              <label className="block">
                <span className="label mb-1 block">Start (UTC)</span>
                <input className={input} type="date" name="period_start" value={period.start} disabled={busy || Boolean(validation)} onChange={(e) => setPeriod({ ...period, start: e.target.value })} />
              </label>
              <label className="block">
                <span className="label mb-1 block">End (UTC)</span>
                <input className={input} type="date" name="period_end" value={period.end} disabled={busy || Boolean(validation)} onChange={(e) => setPeriod({ ...period, end: e.target.value })} />
              </label>
            </div>
          )}
        </section>

        <section aria-labelledby="files-h">
          <h2 id="files-h" className="mb-1 text-[15px] font-semibold text-ink">
            3. Evidence files
          </h2>
          <p className="mb-3 text-[12.5px] text-muted">
            One file per category: CSV, JSON, JSONL or SQLite. The pre-check below runs in your browser and only reads column names; the SAT-SA service is the validator.
          </p>
          <ul className="space-y-2">
            {EVIDENCE_CATEGORIES.map((category) => {
              const file = files[category];
              const check = checks[category];
              return (
                <li key={category} className="rounded-md border border-line bg-paper px-4 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <span className="text-[13.5px] font-medium text-ink">{CATEGORY_LABEL[category]}</span>
                    <label className={cn("inline-flex cursor-pointer items-center gap-2 text-[12.5px]", (busy || validation) && "pointer-events-none opacity-50")}>
                      <FileUp className="size-3.5 text-muted" aria-hidden="true" />
                      <span className="text-brand">{file ? "Replace file" : "Choose file"}</span>
                      <input
                        type="file"
                        className="sr-only"
                        name={category}
                        accept=".csv,.json,.jsonl,.ndjson,.db,.sqlite,.sqlite3"
                        disabled={busy || Boolean(validation)}
                        onChange={(e) => void choose(category, e.target.files?.[0] ?? null)}
                      />
                    </label>
                  </div>
                  {file && (
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-[12.5px]">
                      <span className="mono-id">{file.name}</span>
                      <span className="text-muted">{(file.size / 1024).toFixed(1)} KB</span>
                      {check?.records != null && <span className="text-muted">{check.records} records</span>}
                      {check && check.problems.length === 0 && <Tag tone="brand">Pre-check passed</Tag>}
                      {!busy && !validation && (
                        <button type="button" className="ml-auto text-muted hover:text-ink" aria-label={`Remove ${CATEGORY_LABEL[category]} file`} onClick={() => void choose(category, null)}>
                          <X className="size-3.5" aria-hidden="true" />
                        </button>
                      )}
                    </div>
                  )}
                  {check?.problems.length ? (
                    <ul className="mt-2 space-y-0.5 text-[12px] text-attention-strong">
                      {check.problems.map((p) => (
                        <li key={p} className="flex items-start gap-1.5">
                          <AlertTriangle className="mt-px size-3 shrink-0" aria-hidden="true" />
                          {p}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </section>

        {!validation && (
          <div>
            <Button variant="primary" size="lg" disabled={!ready} onClick={() => void submit()}>
              {busy ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <FileUp className="size-4" aria-hidden="true" />}
              {error ? "Retry submission" : "Submit and validate"}
            </Button>
            {error && error.step !== "run" && <ActionError error={error.info} />}
          </div>
        )}

        {validation && (
          <section aria-labelledby="result-h" className="rounded-md border border-line bg-paper p-5" data-validation={validation.status}>
            <h2 id="result-h" className="flex items-center gap-2 text-[15px] font-semibold text-ink">
              Validation result <Tag tone={validation.status === "valid" ? "brand" : validation.status === "invalid" ? "attention" : "critical"}>{validation.status}</Tag>
            </h2>
            <p className="mt-2 text-[13px] text-ink-2">
              {validation.totals.received ?? 0} received · {validation.totals.accepted ?? 0} accepted · {validation.totals.rejected ?? 0} rejected
              {version ? ` · version ${version.version}` : ""}
            </p>
            {validation.errors.length > 0 && (
              <ul className="mt-3 max-h-60 space-y-1 overflow-y-auto text-[12.5px]">
                {validation.errors.slice(0, 50).map((e, i) => (
                  <li key={i} className="text-ink-2">
                    <span className="font-mono text-muted">{[e.category, e.locator].filter(Boolean).join(" ")}</span> {e.message ?? (Array.isArray(e.reasons) ? e.reasons.join("; ") : "")}
                  </li>
                ))}
                {validation.errors.length > 50 && <li className="text-muted">{validation.errors.length - 50} more</li>}
              </ul>
            )}
            {validation.status === "valid" ? (
              <div className="mt-5 flex flex-wrap items-end gap-3">
                <label className="block">
                  <span className="label mb-1 block">Orchestration</span>
                  <select className={cn(input, "w-56")} value={mode} onChange={(e) => setMode(e.target.value as "graph" | "standard")} disabled={busy}>
                    <option value="graph">LangGraph (checkpointed)</option>
                    <option value="standard">Standard</option>
                  </select>
                </label>
                <Button variant="primary" disabled={busy} onClick={() => void start()}>
                  {busy ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Play className="size-4" aria-hidden="true" />}
                  Start analysis
                </Button>
              </div>
            ) : (
              <p className="mt-4 text-[13px] text-muted">
                This version cannot be analysed. Correct the files and submit again as a new version from{" "}
                <Link className="text-brand hover:underline" href="/workbench/ingest">
                  a fresh ingest
                </Link>
                .
              </p>
            )}
            {error?.step === "run" && <ActionError error={error.info} />}
          </section>
        )}
      </div>

      <aside aria-label="Submission progress" className="lg:sticky lg:top-4 lg:self-start">
        <p className="label mb-3">Progress</p>
        <ol className="space-y-2.5">
          {sequence.map((s) => {
            const state = steps[s] ?? "pending";
            return (
              <li key={s} className="flex items-center gap-2.5 text-[13px]" data-step={s} data-state={state}>
                {state === "done" ? (
                  <Check className="size-4 text-brand" aria-hidden="true" />
                ) : state === "running" ? (
                  <Loader2 className="size-4 animate-spin text-info" aria-hidden="true" />
                ) : state === "failed" ? (
                  <X className="size-4 text-critical" aria-hidden="true" />
                ) : (
                  <CircleDot className="size-4 text-faint" aria-hidden="true" />
                )}
                <span className={state === "pending" ? "text-muted" : "text-ink"}>{STEP_LABEL[s]}</span>
                <span className="sr-only">: {state}</span>
              </li>
            );
          })}
        </ol>
        <p className="mt-5 text-[12px] leading-relaxed text-muted">
          Each step is one call to the SAT-SA service. A retry repeats only unfinished steps with the same idempotency keys, so nothing is created twice.
        </p>
      </aside>
    </div>
  );
}

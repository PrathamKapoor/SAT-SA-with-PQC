import type { Metadata } from "next";
import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";
import { SupervisionLoop } from "@/components/domain/supervision-loop";
import { Tag } from "@/components/ui/badges";
import { Metric, PageHeader, Panel, SectionHeader } from "@/components/ui/layout";
import { getSource } from "@/lib/api";
import { AGENT_LAYER, AGENT_WORKERS, agentKind, workerActivity } from "@/lib/domain/agents";
import { fmtPct, prose } from "@/lib/domain/format";
import { SUPERVISOR_ACTION_LABEL } from "@/lib/domain/labels";
import { loadCore } from "@/lib/model";
import type { AgentSpec } from "@/lib/types/domain";

export const metadata: Metadata = { title: "Agents" };

const LAYERS = ["Ingestion", "Detection", "Assessment", "Trust", "Human authority"] as const;

function AgentRow({ a, activity }: { a: AgentSpec; activity: ReactNode }) {
  return (
    <li className="border-b border-line last:border-0">
      <details className="group">
        <summary className="grid cursor-pointer list-none grid-cols-1 gap-x-6 gap-y-2 px-5 py-3.5 hover:bg-canvas md:grid-cols-[minmax(0,14rem)_minmax(0,1fr)_minmax(0,16rem)_1rem] md:items-center [&::-webkit-details-marker]:hidden">
          <span className="min-w-0">
            <span className="block truncate text-[13.5px] font-semibold text-ink">{a.name}</span>
            <span className="mono-id block truncate">{a.agent_id}</span>
          </span>
          <span className="line-clamp-2 text-[13px] text-ink-2">{prose(a.purpose)}</span>
          <span className="text-[12.5px] text-muted">{activity}</span>
          <ChevronDown className="hidden size-4 text-faint transition-transform group-open:rotate-180 md:block" aria-hidden="true" />
        </summary>
        <dl className="grid gap-x-8 gap-y-3 border-t border-line bg-canvas/60 px-5 py-4 text-[12.5px] sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <dt className="label">Inputs (scope)</dt>
            <dd className="mt-1 font-mono text-[12px] text-ink-2">{a.inputs.join(", ") || "none"}</dd>
          </div>
          <div>
            <dt className="label">Outputs</dt>
            <dd className="mt-1 font-mono text-[12px] text-ink-2">{a.outputs.join(", ") || "none"}</dd>
          </div>
          <div>
            <dt className="label">Evidence references</dt>
            <dd className="mt-1 font-mono text-[12px] text-ink-2">{a.evidence_types.join(", ") || "none"}</dd>
          </div>
          <div>
            <dt className="label">Implementation</dt>
            <dd className="mt-1 font-mono text-[12px] break-all text-ink-2">
              {a.implementation_ref} <span className="text-muted">v{a.version}</span>
            </dd>
          </div>
        </dl>
      </details>
    </li>
  );
}

export default async function AgentsPage() {
  const src = getSource();
  const core = await loadCore();
  const [agents, observations, receipts, audit, validation] = await Promise.all([
    src.listAgents(),
    src.listObservations(),
    src.listTrustReceipts(),
    src.getMetaAudit(),
    src.getValidation(),
  ]);
  const risks = await Promise.all(core.entities.map((e) => src.getRiskProfile(e.id)));
  const corroborated = risks.flatMap((r) => r?.correlation_clusters ?? []).filter((c) => c.corroborated).length;
  const records = core.submissions.reduce((n, s) => n + Object.values(s.declaredCounts).reduce((a, b) => a + (b ?? 0), 0), 0);
  const supervisor = core.runs[0] ? await src.getSupervisorDecision(core.runs[0].id) : null;

  const stageMetric: Record<string, string> = {
    "satsa.ingest": `${core.submissions.filter((s) => s.ingestStatus === "accepted").length} submissions accepted`,
    "satsa.normalize": `${records} records normalized`,
    "satsa.correlation_fusion": `${corroborated} corroborated clusters`,
    "satsa.fusion": `${risks.filter(Boolean).length} risk profiles`,
    "satsa.prioritization": `${core.priorities.length} entities ranked`,
    "satsa.recommendation": `${core.findings.filter((f) => f.recommendation).length} recommendations`,
    "satsa.review_workflow": `${core.decisions.length} decisions recorded`,
    "satsa.trust_provenance": `${receipts.length} receipts signed`,
    "satsa.meta_audit": audit ? (audit.fully_compliant ? "Fully compliant" : "Exceptions found") : "Not run",
    "satsa.evidence_assembly": "Assembles explanations on request",
    "satsa.report_generation": "Renders reports on request",
    "satsa.validation": `${validation?.composition.length ?? 0} composition cases`,
  };

  const activityFor = (a: AgentSpec): ReactNode => {
    const kind = agentKind(a);
    if (kind === "platform") return "Governs the ML platform; no SAT-SA run activity";
    if (kind === "stage") return stageMetric[a.agent_id] ?? "Pipeline stage";
    const w = workerActivity(AGENT_WORKERS[a.agent_id], observations, core.findings);
    return (
      <span>
        <span className="num font-medium text-ink">{w.findings}</span> findings · <span className="num">{w.signal}</span>/{w.observations} runs signalled
        {w.insufficient > 0 && <span> · {w.insufficient} abstained</span>}
        {w.meanConfidence != null && <span> · {fmtPct(w.meanConfidence)} conf.</span>}
      </span>
    );
  };

  const satsa = agents.filter((a) => a.family === "satsa");
  const mlops = agents.filter((a) => a.family === "mlops");
  const workerCount = satsa.filter((a) => agentKind(a) === "worker").length;

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Intelligence"
        title="Agents"
        description="Each agent is a bounded, deterministic component with a declared scope, inputs and evidence outputs. None of them is a language model, and none can make a supervisory decision."
      />

      <Panel className="mb-8 px-5 py-5">
        <dl className="grid grid-cols-2 gap-6 sm:grid-cols-4">
          <Metric label="Registered" value={agents.length} />
          <Metric label="SAT-SA supervisory" value={satsa.length} detail={`${workerCount} analytical, ${satsa.length - workerCount} pipeline`} />
          <Metric label="Retained MLOps" value={mlops.length} detail="govern the ML platform" />
          <Metric label="Implemented" value={agents.filter((a) => a.status === "implemented").length} unit={`of ${agents.length}`} />
        </dl>
      </Panel>

      <section aria-labelledby="loop-h" className="mb-10">
        <SectionHeader id="loop-h" title="Supervision loop" aside={supervisor ? `latest proposal: ${SUPERVISOR_ACTION_LABEL[supervisor.action] ?? supervisor.action}` : undefined} />
        <SupervisionLoop activeAction={supervisor?.action} />
      </section>

      {LAYERS.map((layer) => {
        const inLayer = satsa.filter((a) => (AGENT_LAYER[a.agent_id] ?? "Assessment") === layer);
        if (!inLayer.length) return null;
        return (
          <section key={layer} aria-labelledby={`l-${layer}`} className="mb-8">
            <SectionHeader id={`l-${layer}`} label="SAT-SA" title={layer} aside={`${inLayer.length} agent${inLayer.length === 1 ? "" : "s"}`} />
            <ul className="rounded-md border border-line bg-paper">
              {inLayer.map((a) => (
                <AgentRow key={a.agent_id} a={a} activity={activityFor(a)} />
              ))}
            </ul>
          </section>
        );
      })}

      <section aria-labelledby="l-mlops" className="mb-8">
        <SectionHeader
          id="l-mlops"
          label="QSMLOps"
          title="Retained MLOps agents"
          aside={<Tag tone="neutral">Platform governance</Tag>}
        />
        <ul className="rounded-md border border-line bg-paper">
          {mlops.map((a) => (
            <AgentRow key={a.agent_id} a={a} activity={activityFor(a)} />
          ))}
        </ul>
      </section>
    </div>
  );
}

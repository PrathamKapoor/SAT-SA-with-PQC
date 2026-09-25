import type { Metadata } from "next";
import { ArrowDown, WifiOff } from "lucide-react";
import { SupervisionLoop } from "@/components/domain/supervision-loop";
import { PageHeader, SectionHeader } from "@/components/ui/layout";

export const metadata: Metadata = { title: "Architecture" };

const LAYERS = [
  {
    n: "01",
    name: "Ingestion and normalization",
    what: "CSV, JSON, JSONL and SQLite submissions become canonical, digest-stamped records and a frozen snapshot.",
    modules: ["satsa.ingest.readers", "satsa.ingest.normalize", "satsa.ingest.db_adapter", "satsa.store.dataset"],
  },
  {
    n: "02",
    name: "Analytical workers",
    what: "Sixteen deterministic workers observe the snapshot: execution gaps, negative space, anomalies, peers, coverage, drift and more.",
    modules: ["satsa.analysis.run", "satsa.analysis.workers.*", "satsa.contracts.orchestration"],
  },
  {
    n: "03",
    name: "Correlation, risk and prioritization",
    what: "Findings are correlated across detectors, scored on seven weighted dimensions, ranked, and given a bounded recommendation.",
    modules: ["satsa.analysis.correlation", "satsa.analysis.risk", "satsa.analysis.prioritize", "satsa.analysis.recommend"],
  },
  {
    n: "04",
    name: "TRUST-SAT evidence integrity",
    what: "Runs and findings are signed (ML-DSA-65 over SHA3-256); decisions are digest-bound and hash-chained; a meta-audit sweeps coverage.",
    modules: ["satsa.analysis.trust", "satsa.analysis.canonical", "satsa.analysis.meta_audit", "qsmlops.crypto"],
  },
  {
    n: "05",
    name: "Human presentation and terminal authority",
    what: "Supervisors inspect evidence and record the decision. Agents recommend; only a human decides.",
    modules: ["satsa.analysis.review", "satsa.security", "satsa.ui", "web/ (this interface)"],
  },
];

export default function ArchitecturePage() {
  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Intelligence"
        title="Architecture"
        description="Five layers, one direction of flow, one local database. The platform runs offline: no telemetry feed, no network calls in the analytical pipeline."
      />

      <div className="relative rounded-md border border-dashed border-line-2 bg-paper p-4 md:p-6">
        <p className="label absolute -top-2.5 left-4 flex items-center gap-1.5 bg-paper px-2">
          <WifiOff className="size-3.5" aria-hidden="true" />
          Offline deployment boundary
        </p>
        <ol aria-label="SAT-SA layers, top to bottom" className="space-y-2">
          {LAYERS.map((l, i) => (
            <li key={l.n}>
              <div className="grid gap-x-8 gap-y-3 rounded-md border border-line px-5 py-4 md:grid-cols-[3rem_minmax(0,18rem)_minmax(0,1fr)]">
                <span className="font-mono text-[22px] leading-none font-semibold text-brand">{l.n}</span>
                <div>
                  <p className="text-[15px] font-semibold text-ink">{l.name}</p>
                  <p className="mt-1 text-[13px] leading-relaxed text-muted">{l.what}</p>
                </div>
                <ul className="flex flex-wrap content-start gap-1.5">
                  {l.modules.map((m) => (
                    <li key={m} className="rounded-xs border border-line bg-canvas px-1.5 py-0.5 font-mono text-[11.5px] text-ink-2">
                      {m}
                    </li>
                  ))}
                </ul>
              </div>
              {i < LAYERS.length - 1 && <ArrowDown className="mx-auto my-1 size-4 text-faint" aria-hidden="true" />}
            </li>
          ))}
        </ol>
        <div className="mt-4 grid gap-2 md:grid-cols-2">
          <div className="rounded-md border border-line bg-canvas px-5 py-4">
            <p className="text-[14px] font-semibold text-ink">Local SQLite evidence store</p>
            <p className="mt-1 text-[13px] text-muted">Every layer reads and writes one database. The hash-chained ledger is the source of truth for decisions. Single-writer by design.</p>
          </div>
          <div className="rounded-md border border-line bg-canvas px-5 py-4">
            <p className="text-[14px] font-semibold text-ink">QSMLOps platform (retained)</p>
            <p className="mt-1 text-[13px] text-muted">Post-quantum crypto, evidence ledger, identity and RBAC, and nine MLOps agents that govern the ML platform itself.</p>
          </div>
        </div>
      </div>

      <section aria-labelledby="sup-h" className="mt-10">
        <SectionHeader id="sup-h" title="Supervisor engine" aside="satsa/supervisor/engine.py" />
        <SupervisionLoop />
      </section>

      <section aria-labelledby="ui-h" className="mt-10 grid gap-6 md:grid-cols-2">
        <div>
          <SectionHeader id="ui-h" title="Two interfaces" />
          <p className="text-[13px] leading-relaxed text-ink-2">
            This interface (web/) is the supervisory product surface. The backend also serves its own server-rendered operator UI (python scripts/serve_ui.py) directly over the
            database. Both read the same records; this one reaches them through the API contract in docs/API_CONTRACT.md.
          </p>
        </div>
        <div>
          <SectionHeader title="What SAT-SA is not" as="h3" />
          <p className="text-[13px] leading-relaxed text-ink-2">
            Not a SIEM, not a real-time SOC monitor, not a national telemetry collector, and not an autonomous authority. It analyses periodic submissions and supports a human decision.
          </p>
        </div>
      </section>
    </div>
  );
}

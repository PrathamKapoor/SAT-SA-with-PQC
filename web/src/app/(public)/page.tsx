import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Check, FileSearch, Gavel, Layers, ShieldCheck, X } from "lucide-react";
import { EvidenceHero } from "@/components/public/evidence-field/EvidenceHero";
import { GITHUB_URL } from "@/components/public/site-chrome";
import { buttonClass } from "@/components/ui/button";

export const metadata: Metadata = {
  title: { absolute: "SAT-SA · Supervisory Analytics for SOC Assessment" },
  description:
    "SAT-SA turns periodic CSE submissions into evidence-backed supervisory findings, prioritised for human review and verifiable with post-quantum signatures.",
};

const FLOW = [
  { phase: "Evidence", steps: ["CSE submission", "Ingestion", "Normalization"] },
  { phase: "Analysis", steps: ["Analytical workers", "Correlation", "Risk assessment", "Prioritization"] },
  { phase: "Finding", steps: ["Finding", "Evidence", "Recommendation"] },
  { phase: "Authority", steps: ["Human review", "Decision", "TRUST-SAT verification"] },
];

const CAPABILITIES = [
  {
    icon: FileSearch,
    title: "Finds what the metrics hide",
    body: "Execution gaps such as alerts closed without investigation or escalation, and negative space: evidence that should exist but was never submitted.",
  },
  {
    icon: Layers,
    title: "Explains every score",
    body: "Risk is decomposed across seven weighted dimensions. Each finding carries its statistic, threshold, confidence vector, limitations and source records.",
  },
  {
    icon: Gavel,
    title: "Keeps the human in charge",
    body: "Agents observe and recommend. Only a supervisor records a decision, bound to the exact content of the finding they reviewed.",
  },
  {
    icon: ShieldCheck,
    title: "Proves nothing changed",
    body: "Runs and findings are signed with ML-DSA-65 over SHA3-256 digests. Decisions enter a hash-chained ledger. Tampering is detected at verification.",
  },
];

/** From the repository's README and docs/CLAIMS.md. */
const FACTS = [
  { value: "16", label: "analytical workers", note: "per assessment run" },
  { value: "7", label: "risk dimensions", note: "weighted, decomposable" },
  { value: "32", label: "registered agents", note: "23 supervisory, 9 platform" },
  { value: "0", label: "network calls", note: "in the analytical pipeline" },
];

export default function HomePage() {
  return (
    <>
      <EvidenceHero />

      <section aria-labelledby="what-h" className="border-t border-line">
        <div className="mx-auto grid max-w-[1320px] gap-12 px-5 py-20 md:px-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)] lg:py-28">
          <div>
            <p className="label">What it is</p>
            <h2 id="what-h" className="mt-4 max-w-[14ch] text-[36px] leading-[1.05] font-semibold tracking-[-0.03em] text-ink md:text-[48px]">
              An instrument for supervisors, not another monitor.
            </h2>
          </div>
          <div className="grid gap-10 sm:grid-cols-2">
            <div>
              <p className="label mb-4 text-brand">SAT-SA is</p>
              <ul className="space-y-4 text-[15px] leading-relaxed text-ink-2">
                {[
                  "Periodic: it analyses submissions for an assessment period.",
                  "Offline: it runs air-gapped against a local evidence store.",
                  "Evidence-driven: every finding points to its source records.",
                  "Human-supervised: a supervisor is the terminal authority.",
                ].map((t) => (
                  <li key={t} className="flex gap-3">
                    <Check className="mt-1 size-4 shrink-0 text-brand" aria-hidden="true" />
                    {t}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="label mb-4">SAT-SA is not</p>
              <ul className="space-y-4 text-[15px] leading-relaxed text-muted">
                {["A SIEM or a SOC replacement.", "A real-time or continuous telemetry monitor.", "A national monitoring system.", "An autonomous decision-maker."].map((t) => (
                  <li key={t} className="flex gap-3">
                    <X className="mt-1 size-4 shrink-0 text-faint" aria-hidden="true" />
                    {t}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section id="flow" aria-labelledby="flow-h" className="scroll-mt-16 border-t border-line bg-canvas">
        <div className="mx-auto max-w-[1320px] px-5 py-20 md:px-8 lg:py-28">
          <p className="label">Method</p>
          <h2 id="flow-h" className="mt-4 max-w-[22ch] text-[36px] leading-[1.05] font-semibold tracking-[-0.03em] text-ink md:text-[48px]">
            From a CSE submission to a verifiable decision.
          </h2>
          <ol className="mt-14 grid gap-px overflow-hidden rounded-md border border-line bg-line md:grid-cols-4">
            {FLOW.map((p, i) => (
              <li key={p.phase} className="bg-paper px-6 py-7">
                <p className="font-mono text-[12px] text-brand">{String(i + 1).padStart(2, "0")}</p>
                <p className="mt-2 text-[20px] font-semibold tracking-[-0.01em] text-ink">{p.phase}</p>
                <ol className="mt-5 space-y-2.5">
                  {p.steps.map((s) => (
                    <li key={s} className="flex items-center gap-2.5 text-[14px] text-ink-2">
                      <span aria-hidden="true" className="h-px w-3 bg-line-2" />
                      {s}
                    </li>
                  ))}
                </ol>
              </li>
            ))}
          </ol>
          <Link href="/methodology" className="mt-8 inline-flex items-center gap-1.5 text-[14px] font-medium text-brand hover:text-brand-strong">
            Read the methodology
            <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        </div>
      </section>

      <section aria-labelledby="cap-h" className="border-t border-line">
        <div className="mx-auto max-w-[1320px] px-5 py-20 md:px-8 lg:py-28">
          <h2 id="cap-h" className="sr-only">
            Capabilities
          </h2>
          <ul className="grid gap-x-12 gap-y-14 md:grid-cols-2">
            {CAPABILITIES.map((c) => (
              <li key={c.title} className="grid grid-cols-[2.5rem_minmax(0,1fr)] gap-4 border-t border-ink pt-6">
                <c.icon className="size-6 text-brand" strokeWidth={1.5} aria-hidden="true" />
                <div>
                  <h3 className="text-[22px] leading-snug font-semibold tracking-[-0.015em] text-ink">{c.title}</h3>
                  <p className="mt-3 max-w-lg text-[15px] leading-relaxed text-muted">{c.body}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section aria-labelledby="facts-h" className="border-t border-line bg-brand-tint/50">
        <div className="mx-auto max-w-[1320px] px-5 py-16 md:px-8">
          <h2 id="facts-h" className="label text-brand-strong">
            As implemented
          </h2>
          <dl className="mt-8 grid grid-cols-2 gap-10 md:grid-cols-4">
            {FACTS.map((f) => (
              <div key={f.label}>
                <dt className="sr-only">{f.label}</dt>
                <dd className="num text-[56px] leading-none font-semibold tracking-[-0.04em] text-ink">{f.value}</dd>
                <dd className="mt-3 text-[14px] text-ink-2">{f.label}</dd>
                <dd className="text-[12.5px] text-muted">{f.note}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-10 text-[12px] text-muted">Source: repository README and docs/CLAIMS.md, where every claim cites a test or a measured run.</p>
        </div>
      </section>

      <section aria-labelledby="limits-h" className="border-t border-line">
        <div className="mx-auto grid max-w-[1320px] gap-12 px-5 py-20 md:px-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)] lg:py-28">
          <div>
            <p className="label">Honesty discipline</p>
            <h2 id="limits-h" className="mt-4 text-[32px] leading-[1.1] font-semibold tracking-[-0.03em] text-ink md:text-[40px]">
              What we do not claim.
            </h2>
          </div>
          <ul className="grid gap-6 text-[15px] leading-relaxed text-ink-2 sm:grid-cols-2">
            <li className="border-t border-line pt-4">Validation so far uses synthetic, controlled scenarios. It has not processed NCIIPC or live SOC data.</li>
            <li className="border-t border-line pt-4">Risk weights are a starting hypothesis pending calibration with domain experts.</li>
            <li className="border-t border-line pt-4">Post-quantum signing is pure Python and not side-channel hardened. No hardware token supports ML-DSA yet.</li>
            <li className="border-t border-line pt-4">Trust verification detects tampering when it runs. It does not make storage tamper-proof.</li>
          </ul>
        </div>
      </section>

      <section aria-labelledby="cta-h" className="border-t border-line bg-canvas">
        <div className="mx-auto flex max-w-[1320px] flex-col items-start justify-between gap-6 px-5 py-16 md:flex-row md:items-center md:px-8">
          <h2 id="cta-h" className="max-w-[24ch] text-[28px] leading-tight font-semibold tracking-[-0.02em] text-ink">
            Supervisory access is limited to issued identities.
          </h2>
          <div className="flex gap-3">
            <Link href="/login" className={buttonClass("primary", "lg")}>
              Sign in
              <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
            <a href={GITHUB_URL} target="_blank" rel="noreferrer" className={buttonClass("secondary", "lg")}>
              Source
            </a>
          </div>
        </div>
      </section>
    </>
  );
}

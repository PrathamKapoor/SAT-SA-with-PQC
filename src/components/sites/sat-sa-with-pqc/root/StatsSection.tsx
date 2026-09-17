import { Reveal } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Reveal";
import { AgentCompositionBar } from "@/components/sites/sat-sa-with-pqc/shared/AgentCompositionBar";
import { CoverageGauge } from "@/components/sites/sat-sa-with-pqc/shared/CoverageGauge";
import { StatNumber } from "@/components/sites/sat-sa-with-pqc/shared/StatNumber";
import type { statsContent } from "./content/site";
import { agentCompositionContent, coverageContent } from "./content/demo";

/** The remaining stats (not given their own chart) as a compact divided grid. */
const TEXT_STATS = [
  { value: 16, suffix: "", label: "Analytical workers", detail: "in the default run" },
  { value: 7, suffix: "", label: "Risk dimensions", detail: "decomposable, explainable" },
  { value: 1000, suffix: "+", label: "Tests", detail: "full suite, ~5–10 min" },
  { value: 0, suffix: "", label: "Network calls", detail: "verified offline, full pipeline" },
];

export function StatsSection({ content }: { content: typeof statsContent }) {
  return (
    <section className="relative border-white/10 border-t px-16 py-64 lg:px-80 lg:py-96">
      <div
        aria-hidden="true"
        className="satsa-grid-texture pointer-events-none absolute inset-0 -z-1 opacity-60"
      />
      <Reveal as="p" className="mb-16 font-mono text-caption-20 text-[#7c3aed] uppercase">
        {content.eyebrow}
      </Reveal>
      <Reveal as="h2" className="mb-40 max-w-800 text-balance font-medium text-headline-10">
        {content.title}
      </Reveal>

      <Reveal delay={80} className="overflow-hidden rounded-8 border border-white/10 bg-[#0a0a0a]/90">
        <div className="grid grid-cols-1 lg:grid-cols-[auto_1fr]">
          <div className="flex items-center justify-center gap-24 border-white/10 border-b p-24 lg:border-r lg:border-b-0">
            <CoverageGauge value={coverageContent.value} />
            <div>
              <p className="text-ui text-dark-grey">
                {coverageContent.statements.toLocaleString()} statements &middot; {coverageContent.missed} missed
              </p>
              <p className="text-ui text-dark-grey">{coverageContent.scope}</p>
            </div>
          </div>
          <div className="p-24">
            <p className="mb-16 font-mono text-caption-10 text-white uppercase">Supervisory agents</p>
            <AgentCompositionBar mlops={agentCompositionContent.mlops} satsa={agentCompositionContent.satsa} />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-1 border-white/10 border-t bg-white/10 sm:grid-cols-4">
          {TEXT_STATS.map((stat) => (
            <div key={stat.label} className="bg-[#0a0a0a] p-16 lg:p-24">
              <div className="font-medium text-headline-10 text-white">
                <StatNumber value={stat.value} suffix={stat.suffix} />
              </div>
              <div className="mt-8 font-mono text-caption-10 text-white uppercase">{stat.label}</div>
              <div className="mt-2 text-ui text-dark-grey">{stat.detail}</div>
            </div>
          ))}
        </div>
      </Reveal>
      <p className="mt-16 font-mono text-ui text-dark-grey">{content.source}</p>
    </section>
  );
}

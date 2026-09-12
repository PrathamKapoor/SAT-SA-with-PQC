import { CaButton } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/CaButton";
import { Reveal } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Reveal";
import { EntityRiskChart } from "@/components/sites/sat-sa-with-pqc/shared/EntityRiskChart";
import Prism from "@/components/reactbits/Prism";
import type { heroContent } from "./content/site";
import { entityRiskContent } from "./content/demo";

export function HeroSection({ content }: { content: typeof heroContent }) {
  return (
    <section className="relative overflow-hidden px-16 pt-56 pb-64 lg:px-80 lg:pt-80 lg:pb-96">
      {/* Subtle ambient lighting softened for razor-sharp readability */}
      <div aria-hidden="true" className="satsa-grid-texture pointer-events-none absolute inset-0 -z-2" />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-160 -right-160 -z-1 size-600 rounded-full bg-[#3987e5]/[0.08] blur-[140px]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute top-1/4 -left-80 -z-1 size-400 rounded-full bg-[#34d399]/[0.06] blur-[120px]"
      />

      {/* Subtle Ambient Prism Animation shifted behind header with low opacity */}
      <div className="pointer-events-none absolute right-10 top-20 -z-1 h-[320px] w-[320px] opacity-25 overflow-hidden rounded-full blur-[1px]">
        <Prism
          animationType="rotate"
          timeScale={0.3}
          height={3.5}
          baseWidth={5.5}
          scale={3.2}
          hueShift={0.15}
          colorFrequency={1.2}
          noise={0.2}
          glow={0.8}
          bloom={0.8}
          transparent={true}
        />
      </div>

      {/* Eyebrow: Institutional SIH / NCIIPC Badge */}
      <Reveal as="div" className="mb-20">
        <span className="inline-flex items-center gap-2 rounded-full border border-blue-500/30 bg-blue-500/10 px-12 py-4 font-mono text-caption-20 uppercase tracking-widest text-blue-400">
          <span className="size-2 rounded-full bg-blue-400" />
          SMART INDIA HACKATHON 26157 &middot; NCIIPC
        </span>
      </Reveal>

      {/* Crystal-Clear, High-Contrast Hero Headline */}
      <div className="mb-24 max-w-1000">
        <Reveal as="h1" className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-white leading-tight font-sans">
          Periodic CSE assessments<br className="hidden sm:inline" /> become{" "}
          <span className="text-blue-400">supervisory intelligence.</span>
        </Reveal>
      </div>

      {/* Clear Lede Subtitle */}
      <Reveal as="p" className="mb-40 max-w-700 text-body-20 text-slate-200 leading-relaxed font-sans">
        Turn structured submissions into evidence-backed supervisory decisions.
        Continuous telemetry verification, multi-worker risk fusion, and post-quantum cryptographic trust for critical sector entities.
      </Reveal>

      {/* Action Buttons */}
      <Reveal rise delay={200} className="mb-56 flex flex-wrap items-center gap-16">
        <a
          href="/workbench/overview"
          className="inline-flex items-center gap-8 rounded-8 bg-blue-600 px-24 py-12 font-mono text-caption-20 font-semibold uppercase tracking-wider text-white transition-all hover:bg-blue-500 shadow-[0_0_25px_rgba(59,130,246,0.35)]"
        >
          <span>Launch Supervisory Workbench</span>
          <span>&rarr;</span>
        </a>
        <CaButton
          leftText={content.cta.leftText}
          rightText={content.cta.rightText}
          variant="dark"
          href={content.cta.href}
          external={content.cta.external}
        />
        <a
          href={content.secondaryCta.href}
          className="font-mono text-caption-20 text-slate-300 uppercase underline decoration-slate-600 underline-offset-4 transition-colors hover:text-white"
        >
          {content.secondaryCta.text} &rarr;
        </a>
      </Reveal>

      {/* Flagship data panel */}
      <Reveal delay={250} className="overflow-hidden rounded-8 border border-white/10 bg-[#0a0a0a]/80 backdrop-blur-[2px]">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px]">
          <div className="p-16 lg:p-32">
            <p className="mb-16 font-mono text-caption-10 text-dark-grey uppercase">Who needs attention? &middot; live demo roster</p>
            <EntityRiskChart data={entityRiskContent} />
          </div>
          <div className="grid grid-cols-2 divide-x divide-white/10 border-white/10 border-t lg:grid-cols-1 lg:divide-x-0 lg:divide-y lg:border-t-0 lg:border-l">
            {content.demoStats.map((stat) => (
              <div key={stat.label} className="p-16 lg:p-24">
                <div className="font-medium text-headline-10 text-white">{stat.value}</div>
                <div className="mt-4 font-mono text-caption-10 text-dark-grey uppercase">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="flex flex-col gap-4 border-white/10 border-t px-16 py-10 font-mono text-ui text-dark-grey uppercase sm:flex-row sm:items-center sm:justify-between lg:px-32">
          <span>Live snapshot from the committed demo dataset (scripts/serve_ui.py)</span>
          <span>not production NCIIPC data</span>
        </div>
      </Reveal>
    </section>
  );
}

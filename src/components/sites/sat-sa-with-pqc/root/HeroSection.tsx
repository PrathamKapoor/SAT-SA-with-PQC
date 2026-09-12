import React from "react";
import Link from "next/link";
import { Reveal } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Reveal";
import { EntityRiskChart } from "@/components/sites/sat-sa-with-pqc/shared/EntityRiskChart";
import MaskedHeading from "@/components/reactbits/MaskedHeading";
import Grainient from "@/components/reactbits/Grainient";
import { InteractiveEvidenceHero } from "./InteractiveEvidenceHero";
import type { heroContent } from "./content/site";
import { entityRiskContent } from "./content/demo";
import { ArrowRight, ShieldCheck } from "lucide-react";

export function HeroSection({ content }: { content: typeof heroContent }) {
  return (
    <section className="satsa-hero relative isolate px-16 pt-56 pb-64 lg:px-80 lg:pt-64 lg:pb-80">
      {/* 1. React Bits Grainient Background (Landing Hero Background Only) */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-3 overflow-hidden">
        <Grainient
          className="landing-hero__grainient opacity-70"
          color1="#C7D2FE"
          color2="#67E8F9"
          color3="#E0E7FF"
          lightMode
          timeSpeed={0.06}
          colorBalance={0.08}
          warpStrength={0.22}
          warpFrequency={2.4}
          warpSpeed={0.35}
          warpAmplitude={80}
          blendAngle={18}
          blendSoftness={0.16}
          rotationAmount={95}
          noiseScale={1.1}
          grainAmount={0.025}
          grainScale={1.5}
          grainAnimated={false}
          contrast={1.12}
          gamma={1.0}
          saturation={0.72}
          centerX={0.0}
          centerY={0.0}
          zoom={1.05}
        />
      </div>

      {/* 2. Contrast-safe light veil keeps text clear over the atmospheric field */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 -z-2 bg-gradient-to-b from-white/15 via-white/45 to-[#f7f9fc] backdrop-blur-[0.5px]"
      />
      <div aria-hidden="true" className="satsa-grid-texture pointer-events-none absolute inset-0 -z-1 opacity-20" />

      <div className="satsa-hero__layout">
      <div className="satsa-hero__copy">

      {/* 3. Eyebrow: Institutional SIH / NCIIPC Badge */}
      <Reveal as="div" className="mb-20">
        <span className="inline-flex items-center gap-2 rounded-full border border-blue-500/35 bg-blue-950/50 px-14 py-5 font-mono text-caption-20 uppercase tracking-widest text-blue-300">
          <span className="size-2 rounded-full bg-blue-400 shadow-[0_0_8px_rgba(56,189,248,0.7)]" />
          SMART INDIA HACKATHON 26157 &middot; NCIIPC
        </span>
      </Reveal>

      {/* 4. Main Heading: React Bits MaskedHeading Integration */}
      <div className="mb-20 max-w-1000">
        <MaskedHeading
          text="Supervision, backed by evidence."
          tag="h1"
          mediaType="image"
          src="/sites/sat-sa-with-pqc/root/institutional-mesh.svg"
          fillScale={1.12}
          parallax={8}
          drift={4}
          brightness={0.62}
          saturation={0.78}
          grayscale={false}
          reveal="none"
          trigger="view"
          duration={0.8}
          stagger={0.055}
          align="left"
          weight={700}
          tracking={-0.035}
          lineHeight={0.98}
          textScale={0.15}
          className="text-white"
        />
      </div>

      {/* 5. Supporting Copy */}
      <Reveal as="p" className="mb-16 max-w-700 text-body-20 text-slate-200 leading-relaxed font-sans">
        SAT-SA turns periodic CSE submissions into traceable priorities and evidence-backed decisions for human examiners.
      </Reveal>

      {/* 6. Institutional Capability Line */}
      <Reveal as="div" className="mb-36 flex items-center gap-2 font-mono text-xs text-slate-400">
        <ShieldCheck className="size-3.5 text-blue-400 shrink-0" />
        <span>Offline by design &middot; Periodic assessments &middot; PQC evidence integrity</span>
      </Reveal>

      {/* 7. Action Buttons */}
      <Reveal rise delay={200} className="flex flex-wrap items-center gap-16">
        <Link
          href="/workbench/overview"
          className="inline-flex items-center gap-8 rounded-8 bg-blue-600 px-24 py-12 font-mono text-caption-20 font-semibold uppercase tracking-wider text-white transition-all hover:bg-blue-500 shadow-[0_0_25px_rgba(59,130,246,0.35)]"
        >
          <span>Open Supervisory Workbench</span>
          <ArrowRight className="size-[18px] shrink-0" />
        </Link>
        <Link
          href="/workbench/governance"
          className="font-mono text-caption-20 text-slate-300 uppercase underline decoration-slate-600 underline-offset-4 transition-colors hover:text-white flex items-center gap-1.5"
        >
          <span>View assessment methodology</span>
          <span>&rarr;</span>
        </Link>
      </Reveal>
      </div>
      <InteractiveEvidenceHero />
      </div>

      {/* 8. Flagship Live Demo Data Panel */}
      <Reveal delay={250} className="overflow-hidden rounded-8 border border-white/10 bg-[#0a0a0a]/85 backdrop-blur-[2px]">
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

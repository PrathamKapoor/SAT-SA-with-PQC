import { CaButton } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/CaButton";
import { Reveal } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Reveal";
import { EntityRiskChart } from "@/components/sites/sat-sa-with-pqc/shared/EntityRiskChart";
import type { heroContent } from "./content/site";
import { entityRiskContent } from "./content/demo";

export function HeroSection({ content }: { content: typeof heroContent }) {
  return (
    <section className="relative overflow-hidden px-16 pt-56 pb-64 lg:px-80 lg:pt-80 lg:pb-96">
      {/* Texture + ambient glow, behind everything in this section */}
      <div aria-hidden="true" className="satsa-grid-texture pointer-events-none absolute inset-0 -z-2" />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-160 -right-160 -z-1 size-600 rounded-full bg-[#34d399]/[0.16] blur-[120px]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-80 left-1/4 -z-1 size-400 rounded-full bg-[#3987e5]/[0.10] blur-[100px]"
      />

      <Reveal as="p" className="mb-20 font-mono text-caption-20 uppercase text-[#34d399]">
        {content.eyebrow}
      </Reveal>
      <h1 className="mb-32 max-w-1000 whitespace-pre-line text-balance font-medium text-headline-20">
        <Reveal as="span" className="inline-block">
          {content.title}
        </Reveal>
      </h1>
      <div className="mb-40 max-w-600 text-body-20 text-ghost-grey">
        {content.body.map((paragraph, i) => (
          <Reveal key={i}>{paragraph}</Reveal>
        ))}
      </div>
      <Reveal rise delay={200} className="mb-56 flex flex-wrap items-center gap-16">
        <CaButton
          leftText={content.cta.leftText}
          rightText={content.cta.rightText}
          variant="dark"
          href={content.cta.href}
          external={content.cta.external}
        />
        <a
          href={content.secondaryCta.href}
          className="font-mono text-caption-20 text-white/70 uppercase underline decoration-white/30 underline-offset-4 transition-colors hover:text-white"
        >
          {content.secondaryCta.text} &rarr;
        </a>
      </Reveal>

      {/* Flagship data panel — mirrors the live product's own chart card chrome */}
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

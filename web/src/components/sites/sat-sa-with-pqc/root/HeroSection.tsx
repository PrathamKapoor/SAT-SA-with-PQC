import { Reveal } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Reveal";
import { EntityRiskChart } from "@/components/sites/sat-sa-with-pqc/shared/EntityRiskChart";
import { SatSaHero } from "./hero/SatSaHero";
import type { heroContent } from "./content/site";
import { entityRiskContent } from "./content/demo";

export function HeroSection({ content }: { content: typeof heroContent }) {
  return (
    <>
      <SatSaHero content={content} />

      <section aria-label="Live demo roster" className="px-16 pb-64 lg:px-80 lg:pb-80">
        <Reveal className="overflow-hidden rounded-8 border border-white/10 bg-[#0a0a0a]/85">
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
    </>
  );
}

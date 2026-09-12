import { StatNumber } from "@/components/sites/sat-sa-with-pqc/shared/StatNumber";
import { Reveal } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Reveal";
import type { statsContent } from "./content/site";

export function StatsSection({ content }: { content: typeof statsContent }) {
  return (
    <section className="border-white/10 border-t bg-white/[0.02] px-16 py-72 lg:px-80 lg:py-120">
      <Reveal as="p" className="mb-16 font-mono text-caption-20 text-[#34d399] uppercase">
        {content.eyebrow}
      </Reveal>
      <Reveal as="h2" className="mb-48 max-w-800 text-balance font-medium text-headline-10">
        {content.title}
      </Reveal>
      <div className="grid grid-cols-2 gap-x-24 gap-y-40 lg:grid-cols-3 lg:gap-x-32">
        {content.stats.map((stat, i) => (
          <Reveal key={stat.label} delay={i * 60}>
            <div className="font-medium text-headline-10 text-white">
              <StatNumber value={stat.value} suffix={stat.suffix} />
            </div>
            <div className="mt-8 font-mono text-caption-10 text-white uppercase">{stat.label}</div>
            <div className="mt-2 text-ui text-dark-grey">{stat.detail}</div>
          </Reveal>
        ))}
      </div>
      <p className="mt-48 font-mono text-ui text-dark-grey">{content.source}</p>
    </section>
  );
}

import { Reveal } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Reveal";
import { StatNumber } from "@/components/sites/sat-sa-with-pqc/shared/StatNumber";
import type { agentsContent } from "./content/site";

export function AgentsSection({ content }: { content: typeof agentsContent }) {
  return (
    <section id="agents" className="relative border-white/10 border-t px-16 py-64 lg:px-80 lg:py-96">
      <div aria-hidden="true" className="satsa-grid-texture pointer-events-none absolute inset-0 -z-1 opacity-40" />
      <Reveal as="p" className="mb-16 font-mono text-caption-20 text-[#7c3aed] uppercase">
        {content.eyebrow}
      </Reveal>
      <Reveal as="h2" className="mb-24 max-w-800 text-balance font-medium text-headline-10">
        {content.title}
      </Reveal>
      <Reveal className="mb-40 max-w-800 text-body-20 text-ghost-grey">{content.intro}</Reveal>

      <Reveal delay={80} className="grid grid-cols-1 gap-1 overflow-hidden rounded-8 border border-white/10 bg-white/10 lg:grid-cols-2">
        {content.groups.map((group) => (
          <div key={group.label} className="bg-[#0a0a0a] p-16 lg:p-24">
            <div className="mb-16 flex items-baseline gap-12">
              <span className="font-medium text-headline-10 text-white">
                <StatNumber value={group.count} />
              </span>
              <div>
                <div className="font-mono text-caption-20 text-white uppercase">{group.label}</div>
                <div className="font-mono text-ui text-dark-grey">{group.pkg}</div>
              </div>
            </div>
            <p className="mb-16 text-body-10 text-dark-grey">{group.note}</p>
            <ul className="flex flex-wrap gap-6">
              {group.items.map((item) => (
                <li key={item} className="rounded-4 border border-white/10 bg-white/[0.03] px-8 py-4 font-mono text-ui text-ghost-grey">
                  {item}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </Reveal>

      <Reveal delay={200} className="mt-40">
        <figure className="overflow-hidden rounded-8 border border-white/10 bg-black-deep">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={content.screenshot.src} alt={content.screenshot.alt} className="w-full" loading="lazy" />
          <figcaption className="border-white/10 border-t px-16 py-12 font-mono text-ui text-dark-grey">
            {content.screenshot.caption}
          </figcaption>
        </figure>
      </Reveal>
      <p className="mt-16 font-mono text-ui text-dark-grey">{content.source}</p>
    </section>
  );
}

import { Reveal } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Reveal";
import type { trustContent } from "./content/site";

export function TrustSection({ content }: { content: typeof trustContent }) {
  return (
    <section id="trust" className="border-white/10 border-t px-16 py-72 lg:px-80 lg:py-120">
      <div className="grid grid-cols-1 gap-48 lg:grid-cols-12">
        <div className="lg:col-span-5">
          <Reveal as="p" className="mb-16 font-mono text-caption-20 text-[#34d399] uppercase">
            {content.eyebrow}
          </Reveal>
          <Reveal as="h2" className="mb-24 text-balance font-medium text-headline-10">
            {content.title}
          </Reveal>
          <Reveal className="mb-32 text-body-20 text-ghost-grey">{content.intro}</Reveal>
          <Reveal delay={100} className="border-[#34d399]/30 border-l-2 pl-16 text-body-10 text-dark-grey italic">
            {content.claim}
          </Reveal>
        </div>

        <div className="lg:col-span-7">
          <div className="mb-32 grid grid-cols-2 gap-16">
            {content.pillars.map((pillar, i) => (
              <Reveal key={pillar.label} delay={i * 60} className="rounded-8 border border-white/10 p-16 lg:p-24">
                <div className="mb-4 font-mono text-caption-10 text-dark-grey uppercase">{pillar.label}</div>
                <div className="mb-8 font-mono text-caption-20 text-[#34d399]">{pillar.value}</div>
                <p className="text-ui text-dark-grey">{pillar.detail}</p>
              </Reveal>
            ))}
          </div>
          <Reveal delay={200}>
            <figure className="overflow-hidden rounded-8 border border-white/10 bg-black-deep">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={content.screenshot.src} alt={content.screenshot.alt} className="w-full" loading="lazy" />
              <figcaption className="border-white/10 border-t px-16 py-12 font-mono text-ui text-dark-grey">
                {content.screenshot.caption}
              </figcaption>
            </figure>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

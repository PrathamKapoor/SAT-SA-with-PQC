import { Reveal } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Reveal";
import type { limitationsContent } from "./content/site";

export function LimitationsSection({ content }: { content: typeof limitationsContent }) {
  return (
    <section className="border-white/10 border-t bg-white/[0.02] px-16 py-56 lg:px-80 lg:py-72">
      <div className="max-w-800">
        <Reveal as="p" className="mb-16 font-mono text-caption-20 text-[#34d399] uppercase">
          {content.eyebrow}
        </Reveal>
        <Reveal as="h2" className="mb-12 font-medium text-headline-10">
          {content.title}
        </Reveal>
        <Reveal className="mb-32 text-body-10 text-dark-grey">{content.intro}</Reveal>
        <ul className="flex flex-col gap-12">
          {content.items.map((item, i) => (
            <Reveal key={i} as="li" delay={i * 40} className="flex gap-12 text-body-10 text-dark-grey">
              <span aria-hidden="true" className="mt-2 shrink-0 text-white/30">
                &middot;
              </span>
              <span>{item}</span>
            </Reveal>
          ))}
        </ul>
      </div>
    </section>
  );
}

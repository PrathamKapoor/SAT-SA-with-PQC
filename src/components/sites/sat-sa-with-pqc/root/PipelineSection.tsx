import { Reveal } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Reveal";
import type { pipelineContent } from "./content/site";

export function PipelineSection({ content }: { content: typeof pipelineContent }) {
  return (
    <section id="pipeline" className="border-white/10 border-t px-16 py-72 lg:px-80 lg:py-120">
      <div className="grid grid-cols-1 gap-48 lg:grid-cols-12">
        <div className="lg:col-span-5">
          <Reveal as="p" className="mb-16 font-mono text-caption-20 text-[#34d399] uppercase">
            {content.eyebrow}
          </Reveal>
          <Reveal as="h2" className="mb-24 text-balance font-medium text-headline-10">
            {content.title}
          </Reveal>
          <Reveal className="mb-48 text-body-20 text-ghost-grey">{content.intro}</Reveal>

          <ol className="flex flex-col">
            {content.stages.map((stage, i) => (
              <Reveal key={stage.num} as="li" delay={i * 60} className="relative flex gap-16 pb-32 pl-4 last:pb-0">
                {i < content.stages.length - 1 ? (
                  <span aria-hidden="true" className="absolute top-24 bottom-0 left-15 w-1 bg-white/10" />
                ) : null}
                <span className="relative z-1 flex size-30 shrink-0 items-center justify-center rounded-full border border-[#34d399]/40 bg-black font-mono text-caption-10 text-[#34d399]">
                  {stage.num}
                </span>
                <div className="pt-4">
                  <h3 className="mb-4 font-mono text-caption-20 text-white uppercase">{stage.title}</h3>
                  <p className="text-body-10 text-dark-grey">{stage.body}</p>
                </div>
              </Reveal>
            ))}
          </ol>
        </div>

        <Reveal delay={150} className="lg:col-span-7">
          <figure className="overflow-hidden rounded-8 border border-white/10 bg-black-deep">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={content.screenshot.src} alt={content.screenshot.alt} className="w-full" loading="lazy" />
            <figcaption className="border-white/10 border-t px-16 py-12 font-mono text-ui text-dark-grey">
              {content.screenshot.caption}
            </figcaption>
          </figure>
        </Reveal>
      </div>
    </section>
  );
}

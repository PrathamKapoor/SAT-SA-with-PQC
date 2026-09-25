import { Reveal } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Reveal";
import {
  AnalyzeIcon,
  CorrelateIcon,
  IngestIcon,
  RecommendIcon,
  ReviewIcon,
  VerifyIcon,
} from "@/components/sites/sat-sa-with-pqc/shared/icons";
import type { pipelineContent } from "./content/site";

const ICONS = {
  ingest: IngestIcon,
  analyze: AnalyzeIcon,
  correlate: CorrelateIcon,
  recommend: RecommendIcon,
  review: ReviewIcon,
  verify: VerifyIcon,
} as const;

export function PipelineSection({ content }: { content: typeof pipelineContent }) {
  return (
    <section id="pipeline" className="border-white/10 border-t px-16 py-64 lg:px-80 lg:py-96">
      <div className="mb-40 grid grid-cols-1 gap-24 lg:grid-cols-12 lg:gap-48">
        <div className="lg:col-span-5">
          <Reveal as="p" className="mb-16 font-mono text-caption-20 text-[#7c3aed] uppercase">
            {content.eyebrow}
          </Reveal>
          <Reveal as="h2" className="text-balance font-medium text-headline-10">
            {content.title}
          </Reveal>
        </div>
        <Reveal delay={80} className="lg:col-span-7">
          <p className="text-body-20 text-ghost-grey">{content.intro}</p>
        </Reveal>
      </div>

      {/* Connected step flow: a horizontal row on desktop, joined by a line; stacks on mobile. */}
      <div className="relative mb-40 grid grid-cols-2 gap-x-16 gap-y-32 sm:grid-cols-3 lg:grid-cols-6 lg:gap-x-8">
        <div aria-hidden="true" className="absolute inset-x-0 top-19 hidden h-px bg-white/10 lg:block" />
        {content.stages.map((stage, i) => {
          const Icon = ICONS[stage.icon];
          return (
            <Reveal key={stage.num} delay={i * 60} className="relative flex flex-col gap-12">
              <span className="relative z-1 flex size-38 items-center justify-center rounded-full border border-[#7c3aed]/30 bg-[#0a0a0a] text-[#7c3aed]">
                <Icon className="size-16" />
              </span>
              <div>
                <p className="mb-4 font-mono text-ui text-dark-grey">{stage.num}</p>
                <h3 className="mb-4 font-mono text-caption-10 text-white uppercase">{stage.title}</h3>
                <p className="text-ui text-dark-grey">{stage.body}</p>
              </div>
            </Reveal>
          );
        })}
      </div>

      <Reveal delay={150}>
        <figure className="overflow-hidden rounded-8 border border-white/10 bg-black-deep">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={content.screenshot.src} alt={content.screenshot.alt} className="w-full" loading="lazy" />
          <figcaption className="border-white/10 border-t px-16 py-12 font-mono text-ui text-dark-grey">
            {content.screenshot.caption}
          </figcaption>
        </figure>
      </Reveal>
    </section>
  );
}

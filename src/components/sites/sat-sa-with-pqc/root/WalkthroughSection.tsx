import { Reveal } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Reveal";
import { FindingWalkthrough } from "./FindingWalkthrough";
import type { findingWalkthroughContent } from "./content/demo";
import type { walkthroughSectionContent } from "./content/walkthrough";

export function WalkthroughSection({
  content,
  finding,
}: {
  content: typeof walkthroughSectionContent;
  finding: typeof findingWalkthroughContent;
}) {
  return (
    <section id="see-it-work" className="relative border-white/10 border-t px-16 py-64 lg:px-80 lg:py-96">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute top-0 right-0 -z-1 size-500 rounded-full bg-[#34d399]/[0.05] blur-[120px]"
      />
      <Reveal as="p" className="mb-16 font-mono text-caption-20 text-[#34d399] uppercase">
        {content.eyebrow}
      </Reveal>
      <Reveal as="h2" className="mb-16 max-w-800 text-balance font-medium text-headline-10">
        {content.title}
      </Reveal>
      <Reveal className="mb-40 max-w-800 text-body-20 text-ghost-grey">{content.intro}</Reveal>
      <Reveal delay={100}>
        <FindingWalkthrough content={finding} />
      </Reveal>
    </section>
  );
}

import { CheckIcon, DashIcon } from "@/components/sites/sat-sa-with-pqc/shared/icons";
import { Reveal } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Reveal";
import type { identityContent } from "./content/site";

export function IdentitySection({ content }: { content: typeof identityContent }) {
  return (
    <section id="mission" className="border-white/10 border-t px-16 py-72 lg:px-80 lg:py-120">
      <Reveal as="p" className="mb-16 font-mono text-caption-20 text-[#34d399] uppercase">
        {content.eyebrow}
      </Reveal>
      <Reveal as="h2" className="mb-48 max-w-800 text-balance font-medium text-headline-10">
        {content.title}
      </Reveal>
      <div className="grid grid-cols-1 gap-32 lg:grid-cols-2">
        <Reveal>
          <ul className="flex flex-col gap-16">
            {content.is.map((line, i) => (
              <li key={i} className="flex gap-12 text-body-10 text-ghost-grey">
                <CheckIcon className="mt-2 size-16 shrink-0 text-[#34d399]" />
                <span>{line}</span>
              </li>
            ))}
          </ul>
        </Reveal>
        <Reveal delay={100}>
          <ul className="flex flex-col gap-16">
            {content.isNot.map((line, i) => (
              <li key={i} className="flex gap-12 text-body-10 text-dark-grey">
                <DashIcon className="mt-2 size-16 shrink-0 text-dark-grey" />
                <span>{line}</span>
              </li>
            ))}
          </ul>
        </Reveal>
      </div>
    </section>
  );
}

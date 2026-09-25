import { Reveal } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Reveal";
import type { screenshotsContent } from "./content/screenshots";

export function ScreenshotsSection({ content }: { content: typeof screenshotsContent }) {
  return (
    <section
      id="screenshots"
      className="border-white/10 border-t bg-[linear-gradient(180deg,rgba(255,255,255,0.03),rgba(255,255,255,0)_60%)] px-16 py-56 lg:px-80 lg:py-80"
    >
      <Reveal as="p" className="mb-16 font-mono text-caption-20 text-[#7c3aed] uppercase">
        {content.eyebrow}
      </Reveal>
      <Reveal as="h2" className="mb-16 max-w-800 text-balance font-medium text-headline-10">
        {content.title}
      </Reveal>
      <Reveal className="mb-48 max-w-800 text-body-20 text-ghost-grey">{content.intro}</Reveal>

      <div className="grid grid-cols-1 gap-24 lg:grid-cols-2">
        {content.items.map((item, i) => (
          <Reveal key={item.src} delay={i * 80}>
            <figure className="group overflow-hidden rounded-8 border border-white/10 bg-black-deep transition-colors hover:border-[#7c3aed]/40">
              <div className="flex h-24 items-center gap-6 border-white/10 border-b px-12">
                <span className="size-8 rounded-full bg-white/15" />
                <span className="size-8 rounded-full bg-white/15" />
                <span className="size-8 rounded-full bg-white/15" />
              </div>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={item.src} alt={item.alt} className="w-full transition-transform duration-500 group-hover:scale-[1.02]" loading="lazy" />
              <figcaption className="border-white/10 border-t px-16 py-12 font-mono text-ui text-dark-grey">{item.caption}</figcaption>
            </figure>
          </Reveal>
        ))}
      </div>
    </section>
  );
}

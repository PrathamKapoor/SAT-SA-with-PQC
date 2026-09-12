import { CaButton } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/CaButton";
import { Reveal } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Reveal";
import type { heroContent } from "./content/site";

export function HeroSection({ content }: { content: typeof heroContent }) {
  return (
    <section className="relative overflow-hidden px-16 pt-64 pb-72 lg:px-80 lg:pt-120 lg:pb-160">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 -z-1 bg-[radial-gradient(circle_at_top_right,rgba(52,211,153,0.12),transparent_55%)]"
      />
      <Reveal as="p" className="mb-20 font-mono text-caption-20 uppercase text-[#34d399]">
        {content.eyebrow}
      </Reveal>
      <h1 className="mb-32 max-w-1000 whitespace-pre-line text-balance font-medium text-headline-20">
        <Reveal as="span" className="inline-block">
          {content.title}
        </Reveal>
      </h1>
      <div className="mb-48 max-w-600 text-body-20 text-ghost-grey">
        {content.body.map((paragraph, i) => (
          <Reveal key={i}>{paragraph}</Reveal>
        ))}
      </div>
      <Reveal rise delay={200} className="mb-64 flex flex-wrap items-center gap-16">
        <CaButton
          leftText={content.cta.leftText}
          rightText={content.cta.rightText}
          variant="dark"
          href={content.cta.href}
          external={content.cta.external}
        />
        <a
          href={content.secondaryCta.href}
          className="font-mono text-caption-20 text-white/70 uppercase underline decoration-white/30 underline-offset-4 transition-colors hover:text-white"
        >
          {content.secondaryCta.text} &rarr;
        </a>
      </Reveal>
      <Reveal delay={300} className="grid max-w-800 grid-cols-2 gap-x-32 gap-y-24 border-white/10 border-t pt-32 sm:grid-cols-4">
        {content.demoStats.map((stat) => (
          <div key={stat.label}>
            <div className="font-medium text-headline-10 text-white">{stat.value}</div>
            <div className="mt-4 font-mono text-caption-10 text-dark-grey uppercase">{stat.label}</div>
          </div>
        ))}
      </Reveal>
      <p className="mt-16 max-w-800 font-mono text-ui text-dark-grey">
        Live snapshot from the committed demo dataset (scripts/serve_ui.py) — not production NCIIPC data.
      </p>
    </section>
  );
}

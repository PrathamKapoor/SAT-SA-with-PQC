import { cn } from "@/lib/utils";
import { Reveal } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Reveal";
import type { validationContent } from "./content/site";

const STATUS_STYLE: Record<string, string> = {
  verified: "text-[#34d399] border-[#34d399]/30",
  "verified, scoped": "text-[#34d399] border-[#34d399]/30",
  simulated: "text-white/70 border-white/20",
  pending: "text-dark-grey border-white/10",
};

export function ValidationSection({ content }: { content: typeof validationContent }) {
  return (
    <section id="validation" className="border-white/10 border-t px-16 py-72 lg:px-80 lg:py-120">
      <Reveal as="p" className="mb-16 font-mono text-caption-20 text-[#34d399] uppercase">
        {content.eyebrow}
      </Reveal>
      <Reveal as="h2" className="mb-24 max-w-800 text-balance font-medium text-headline-10">
        {content.title}
      </Reveal>
      <Reveal className="mb-48 max-w-800 text-body-20 text-ghost-grey">{content.intro}</Reveal>

      <div className="flex flex-col divide-y divide-white/10 border-white/10 border-t">
        {content.rows.map((row, i) => (
          <Reveal key={row.label} delay={i * 40} className="grid grid-cols-1 gap-x-24 gap-y-8 py-24 lg:grid-cols-12 lg:items-center">
            <div className="font-mono text-caption-20 text-white uppercase lg:col-span-3">{row.label}</div>
            <div className="lg:col-span-2">
              <span className={cn("rounded-4 border px-8 py-2 font-mono text-ui uppercase", STATUS_STYLE[row.status] ?? "text-dark-grey border-white/10")}>
                {row.status}
              </span>
            </div>
            <p className="text-body-10 text-dark-grey lg:col-span-7">{row.detail}</p>
          </Reveal>
        ))}
      </div>
      <p className="mt-24 font-mono text-ui text-dark-grey">{content.source}</p>
    </section>
  );
}

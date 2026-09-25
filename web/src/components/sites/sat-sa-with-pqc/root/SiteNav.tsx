import { CaButton } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/CaButton";
import type { navContent } from "./content/site";

/** Simple sticky top nav: logo, in-page anchors (lg+), and a GitHub CTA always visible. */
export function SiteNav({ content }: { content: typeof navContent }) {
  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/85 shadow-[0_1px_0_rgba(15,23,42,0.04)] backdrop-blur-md">
      <nav aria-label="Primary" className="flex min-h-64 items-center justify-between gap-16 px-16 py-10 lg:px-80">
        <a href={content.homeHref} aria-label={content.logoLabel} className="flex items-center gap-8 font-mono text-caption-20 uppercase text-white transition-colors hover:text-violet-200">
          <span aria-hidden="true" className="inline-block size-8 rounded-full bg-[#7c3aed]" />
          SAT&middot;SA
        </a>
        <ul className="hidden items-center gap-24 font-mono text-caption-10 uppercase text-white/60 lg:flex">
          {content.links.map((link) => (
            <li key={link.href}>
              <a href={link.href} className="rounded-4 px-4 py-3 transition-colors hover:bg-white/5 hover:text-white">
                {link.label}
              </a>
            </li>
          ))}
        </ul>
        <CaButton leftText={content.cta.label} variant="dark" href={content.cta.href} external={content.cta.external} className="shrink-0 *:data-text:border *:data-text:border-slate-300 *:data-text:bg-white *:data-text:text-slate-950 hover:*:data-text:border-violet-400 hover:*:data-text:bg-violet-50" />
      </nav>
    </header>
  );
}

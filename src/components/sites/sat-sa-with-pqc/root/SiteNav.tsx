import { CaButton } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/CaButton";
import type { navContent } from "./content/site";

/** Simple sticky top nav: logo, in-page anchors (lg+), and a GitHub CTA always visible. */
export function SiteNav({ content }: { content: typeof navContent }) {
  return (
    <header className="sticky top-0 z-20 border-white/10 border-b bg-black-deep">
      <nav aria-label="Primary" className="flex items-center justify-between gap-16 px-16 py-12 lg:px-80">
        <a href={content.homeHref} aria-label={content.logoLabel} className="flex items-center gap-8 font-mono text-caption-20 uppercase text-white">
          <span aria-hidden="true" className="inline-block size-8 rounded-full bg-[#34d399]" />
          SAT&middot;SA
        </a>
        <ul className="hidden items-center gap-24 font-mono text-caption-10 uppercase text-white/60 lg:flex">
          {content.links.map((link) => (
            <li key={link.href}>
              <a href={link.href} className="transition-colors hover:text-white">
                {link.label}
              </a>
            </li>
          ))}
        </ul>
        <CaButton leftText={content.cta.label} variant="dark" href={content.cta.href} external={content.cta.external} className="shrink-0" />
      </nav>
    </header>
  );
}

import { ExternalLinkIcon } from "@/components/sites/sat-sa-with-pqc/shared/icons";
import type { footerContent } from "./content/site";

export function SiteFooter({ content }: { content: typeof footerContent }) {
  return (
    <footer className="border-white/10 border-t px-16 py-48 lg:px-80">
      <div className="flex flex-col gap-24 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <a
            href={content.repo.href}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-8 font-mono text-caption-20 text-white uppercase transition-colors hover:text-[#7c3aed]"
          >
            {content.repo.label}
            <ExternalLinkIcon className="size-14" />
          </a>
          <p className="mt-8 font-mono text-ui text-dark-grey">
            {content.packages.map((pkg) => `${pkg.name} ${pkg.version}`).join(" · ")}
          </p>
        </div>
        <div className="font-mono text-ui text-dark-grey lg:text-right">
          <p>
            {content.license.label} &middot; {content.license.author}
          </p>
          <p className="mt-4">{content.program}</p>
        </div>
      </div>
    </footer>
  );
}

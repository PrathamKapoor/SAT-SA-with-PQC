import Link from "next/link";
import { LogoMark } from "@/components/sites/contentarchitecture-dev/shared/icons";
import { AWARDS, FOOTER_LINKS } from "@/components/sites/contentarchitecture-dev/root/content";

export function SiteFooter() {
  return (
    <footer className="bg-background px-6 py-16 lg:px-16 lg:py-20">
      <div className="mx-auto flex max-w-6xl flex-col gap-12">
        <div className="flex flex-col gap-8 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex flex-col gap-4">
            <Link href="/" className="flex items-center gap-2 font-medium">
              <LogoMark className="size-7" />
              <span>The Content Architecture</span>
            </Link>
            <p className="max-w-xs text-sm text-muted-foreground">
              Full-stack kit for Next.js and Astro.
            </p>
            <div className="flex items-center gap-4 pt-2">
              {AWARDS.map((award) => (
                <a
                  key={award.label}
                  href={award.href}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-muted-foreground underline decoration-dashed underline-offset-4 transition-colors hover:text-tertiary"
                >
                  {award.label}
                </a>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-12 sm:flex-row lg:gap-24">
            <nav className="flex flex-col gap-3">
              {FOOTER_LINKS.primary.map((link) => (
                <a
                  key={link.label}
                  href={link.href}
                  className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  {link.label}
                </a>
              ))}
            </nav>
            <nav className="flex flex-col gap-3">
              {FOOTER_LINKS.legal.map((link) => (
                <a
                  key={link.label}
                  href={link.href}
                  className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  {link.label}
                </a>
              ))}
            </nav>
          </div>
        </div>

        <div className="flex flex-col gap-4 border-t border-border pt-8 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <p>&copy; The Content Architecture</p>
          <a
            href="https://www.edoardolunardi.dev"
            target="_blank"
            rel="noreferrer"
            className="uppercase tracking-widest opacity-70 transition-opacity hover:opacity-100"
          >
            Built by edoardolunardi.dev
          </a>
        </div>
      </div>
    </footer>
  );
}

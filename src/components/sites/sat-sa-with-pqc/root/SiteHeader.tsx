"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { ShieldMark } from "@/components/sites/sat-sa-with-pqc/shared/icons";
import { GITHUB_URL, NAV_LINKS } from "@/components/sites/sat-sa-with-pqc/root/content";

export function SiteHeader() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={cn(
        "sticky top-0 z-50 border-b border-border bg-background/90 backdrop-blur-md transition-shadow",
        scrolled && "shadow-lg"
      )}
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 lg:px-8">
        <Link href="/" className="flex items-center gap-2">
          <ShieldMark className="size-7" />
          <span className="flex flex-col leading-none">
            <span className="font-mono text-sm font-semibold tracking-widest">
              SAT<span className="text-primary">&middot;</span>SA
            </span>
            <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              Supervisory Analytics
            </span>
          </span>
        </Link>

        <nav className="hidden items-center gap-1 lg:flex">
          {NAV_LINKS.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="rounded-lg px-3 py-2 font-mono text-xs uppercase tracking-widest text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noreferrer"
            className="hidden rounded-full bg-primary px-4 py-2 font-mono text-xs font-semibold uppercase tracking-widest text-primary-foreground transition-opacity hover:opacity-90 sm:inline-flex"
          >
            View source
          </a>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label="Toggle menu"
            className="inline-flex size-9 items-center justify-center rounded-full border border-border text-foreground lg:hidden"
          >
            {open ? <X className="size-4" /> : <Menu className="size-4" />}
          </button>
        </div>
      </div>

      {open && (
        <div className="border-t border-border bg-background p-4 lg:hidden">
          <nav className="flex flex-col gap-1">
            {NAV_LINKS.map((link) => (
              <a
                key={link.label}
                href={link.href}
                onClick={() => setOpen(false)}
                className="rounded-lg px-3 py-2 font-mono text-xs uppercase tracking-widest text-muted-foreground hover:bg-accent hover:text-foreground"
              >
                {link.label}
              </a>
            ))}
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noreferrer"
              onClick={() => setOpen(false)}
              className="mt-2 rounded-full bg-primary px-4 py-2 text-center font-mono text-xs font-semibold uppercase tracking-widest text-primary-foreground"
            >
              View source
            </a>
          </nav>
        </div>
      )}
    </header>
  );
}

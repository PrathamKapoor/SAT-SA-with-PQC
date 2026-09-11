"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { LogoMark } from "@/components/sites/contentarchitecture-dev/shared/icons";
import { NAV_LINKS } from "@/components/sites/contentarchitecture-dev/root/content";

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
    <header className="fixed inset-x-0 top-0 z-50 flex justify-center p-4 lg:p-6">
      <div
        className={cn(
          "flex w-full max-w-6xl items-center justify-between gap-4 rounded-2xl border border-border bg-background/85 px-4 py-3 backdrop-blur-md transition-shadow",
          scrolled && "shadow-lg"
        )}
      >
        <Link href="/" className="flex items-center gap-2 font-medium">
          <LogoMark className="size-7" />
          <span className="hidden sm:inline">The Content Architecture</span>
        </Link>

        <nav className="hidden items-center gap-1 lg:flex">
          {NAV_LINKS.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <a
            href="#pricing"
            className="hidden rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 sm:inline-flex"
          >
            Get access
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
        <div className="absolute inset-x-4 top-[calc(100%+0.5rem)] rounded-2xl border border-border bg-background p-4 shadow-xl lg:hidden">
          <nav className="flex flex-col gap-1">
            {NAV_LINKS.map((link) => (
              <a
                key={link.label}
                href={link.href}
                onClick={() => setOpen(false)}
                className="rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
              >
                {link.label}
              </a>
            ))}
            <a
              href="#pricing"
              onClick={() => setOpen(false)}
              className="mt-2 rounded-full bg-primary px-4 py-2 text-center text-sm font-medium text-primary-foreground"
            >
              Get access
            </a>
          </nav>
        </div>
      )}
    </header>
  );
}

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Wordmark } from "@/components/brand";
import { buttonClass } from "@/components/ui/button";

export const GITHUB_URL = "https://github.com/PrathamKapoor/SAT-SA-with-PQC";

const LINKS = [
  { href: "/", label: "Product" },
  { href: "/methodology", label: "Methodology" },
  { href: "/security", label: "Security" },
  { href: GITHUB_URL, label: "Source", external: true },
];

export function PublicNav() {
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-paper/90 backdrop-blur-md">
      <nav aria-label="Public" className="mx-auto flex h-16 max-w-[1320px] items-center gap-8 px-5 md:px-8">
        <Link href="/" aria-label="SAT-SA home" className="rounded-sm">
          <Wordmark />
        </Link>
        <ul className="hidden items-center gap-7 md:flex">
          {LINKS.map((l) => (
            <li key={l.href}>
              {l.external ? (
                <a href={l.href} target="_blank" rel="noreferrer" className="text-[13.5px] text-ink-2 hover:text-ink">
                  {l.label}
                </a>
              ) : (
                <Link href={l.href} className="text-[13.5px] text-ink-2 hover:text-ink">
                  {l.label}
                </Link>
              )}
            </li>
          ))}
        </ul>
        <Link href="/login" className={buttonClass("primary", "md", "ml-auto")}>
          Sign in
          <ArrowRight className="size-3.5" aria-hidden="true" />
        </Link>
      </nav>
    </header>
  );
}

export function PublicFooter() {
  return (
    <footer className="border-t border-line bg-canvas">
      <div className="mx-auto grid max-w-[1320px] gap-10 px-5 py-12 md:grid-cols-[minmax(0,1.4fr)_repeat(3,minmax(0,1fr))] md:px-8">
        <div>
          <Wordmark sub />
          <p className="mt-4 max-w-sm text-[13px] leading-relaxed text-muted">
            A periodic, offline, evidence-driven supervisory analytics system for SOC assessment. Built for Smart India Hackathon problem 26157.
          </p>
        </div>
        <div>
          <p className="label mb-3">Product</p>
          <ul className="space-y-2 text-[13px]">
            <li>
              <Link href="/" className="text-ink-2 hover:text-ink">
                Overview
              </Link>
            </li>
            <li>
              <Link href="/methodology" className="text-ink-2 hover:text-ink">
                Methodology
              </Link>
            </li>
            <li>
              <Link href="/security" className="text-ink-2 hover:text-ink">
                Security and trust
              </Link>
            </li>
          </ul>
        </div>
        <div>
          <p className="label mb-3">Access</p>
          <ul className="space-y-2 text-[13px]">
            <li>
              <Link href="/login" className="text-ink-2 hover:text-ink">
                Sign in
              </Link>
            </li>
          </ul>
        </div>
        <div>
          <p className="label mb-3">Research</p>
          <ul className="space-y-2 text-[13px]">
            <li>
              <a href={GITHUB_URL} target="_blank" rel="noreferrer" className="text-ink-2 hover:text-ink">
                Source and documentation
              </a>
            </li>
            <li>
              <a href={`${GITHUB_URL}/blob/main/docs/CLAIMS.md`} target="_blank" rel="noreferrer" className="text-ink-2 hover:text-ink">
                Claims and evidence
              </a>
            </li>
          </ul>
        </div>
      </div>
      <div className="border-t border-line">
        <p className="mx-auto max-w-[1320px] px-5 py-4 text-[12px] text-faint md:px-8">MIT licence. No supervisory data is published on this site.</p>
      </div>
    </footer>
  );
}

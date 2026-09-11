import Link from "next/link";
import { ShieldMark } from "@/components/sites/sat-sa-with-pqc/shared/icons";
import { GITHUB_URL } from "@/components/sites/sat-sa-with-pqc/root/content";

export function SiteFooter() {
  return (
    <footer className="px-6 py-16 lg:px-8">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-4 text-center">
        <Link href="/" className="flex items-center gap-2">
          <ShieldMark className="size-6" />
          <span className="font-mono text-sm font-semibold tracking-widest">
            SAT<span className="text-primary">&middot;</span>SA
          </span>
        </Link>
        <p className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
          SAT-SA v0.1.0 &middot; air-gapped &middot; ML-DSA-65 + ML-KEM-768
        </p>
        <p className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground/70">
          National-security-grade supervisory analytics
        </p>
        <div className="mt-4 flex items-center gap-4 text-xs text-muted-foreground">
          <a href={GITHUB_URL} target="_blank" rel="noreferrer" className="hover:text-foreground">
            GitHub
          </a>
          <span className="h-3 w-px bg-border" />
          <span>MIT License &middot; Pratham Kapoor</span>
        </div>
      </div>
    </footer>
  );
}

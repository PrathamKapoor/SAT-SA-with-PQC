import { cn } from "@/lib/utils";

/**
 * SAT-SA mark: an evidence set (three points) resolving into one verified
 * finding (the square). Drawn, not a font glyph.
 */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={cn("size-6", className)}>
      <rect x="0.5" y="0.5" width="23" height="23" rx="4" className="fill-ink" />
      <circle cx="6.5" cy="7.5" r="1.6" className="fill-white/55" />
      <circle cx="6.5" cy="16.5" r="1.6" className="fill-white/55" />
      <circle cx="10.5" cy="12" r="1.6" className="fill-white/80" />
      <path d="M11.5 12h3" className="stroke-white/70" strokeWidth="1.2" />
      <rect x="14.5" y="9" width="6" height="6" rx="1" className="fill-[#8f7bf0]" />
    </svg>
  );
}

export function Wordmark({ className, sub }: { className?: string; sub?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <BrandMark />
      <span className="leading-none">
        <span className="block font-mono text-[13px] font-semibold tracking-[0.14em] text-ink">SAT·SA</span>
        {sub && <span className="mt-1 block text-[11px] text-muted">Supervisory Analytics</span>}
      </span>
    </span>
  );
}

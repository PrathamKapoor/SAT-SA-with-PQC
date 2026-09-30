import { cn } from "@/lib/utils";

/**
 * TRUST-SAT mark: a shield on the engine body holding the verified record (the
 * tick) of a signed evidence chain. The same design as the site icon, in the
 * simplified cut that stays legible at small sizes. Drawn, not a font glyph.
 */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" aria-hidden="true" className={cn("size-6", className)}>
      <rect x="2" y="2" width="60" height="60" rx="13" fill="#0F1B3D" />
      <rect x="2" y="2" width="60" height="60" rx="13" fill="none" stroke="#7C3AED" strokeWidth="4" />
      <path d="M32 9 50 15.5v15C50 42.4 42.6 50.2 32 55 21.4 50.2 14 42.4 14 30.5v-15z" fill="#FFFFFF" />
      <circle cx="32" cy="32" r="11" fill="#6D28D9" />
      <path d="m26.8 32.4 3.7 3.7 6.8-7.3" fill="none" stroke="#FFFFFF" strokeWidth="4.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Wordmark({ className, sub }: { className?: string; sub?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <BrandMark />
      <span className="leading-none">
        <span className="block font-mono text-[13px] font-semibold tracking-[0.14em] text-ink">TRUST-SAT</span>
        {sub && <span className="mt-1 block text-[11px] text-muted">Supervisory Analytics</span>}
      </span>
    </span>
  );
}

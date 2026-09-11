import { TRUST_CELLS, TRUST_CLAIM } from "@/components/sites/sat-sa-with-pqc/root/content";

export function TrustSection() {
  return (
    <section id="trust" className="border-b border-border px-6 py-20 lg:px-8 lg:py-28">
      <div className="mx-auto max-w-5xl">
        <p className="mb-2 font-mono text-xs uppercase tracking-widest text-primary">
          05 / TRUST-SAT
        </p>
        <h2 className="mb-4 text-balance text-3xl font-light lg:text-4xl">
          Detection of tampering, not tamper-proofness.
        </h2>
        <p className="mb-12 max-w-2xl text-sm leading-relaxed text-muted-foreground">
          {TRUST_CLAIM}
        </p>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {TRUST_CELLS.map((cell) => (
            <div
              key={cell.label}
              className="rounded-2xl border-2 border-primary/30 bg-card p-6 shadow-sm"
            >
              <p className="mb-2 font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                {cell.label}
              </p>
              <p className="mb-1 text-lg font-medium">{cell.value}</p>
              <p className="text-xs text-muted-foreground">{cell.meta}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

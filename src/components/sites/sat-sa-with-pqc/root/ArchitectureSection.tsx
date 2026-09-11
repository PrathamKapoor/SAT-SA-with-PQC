import { ARCHITECTURE_FLOW } from "@/components/sites/sat-sa-with-pqc/root/content";

export function ArchitectureSection() {
  return (
    <section id="architecture" className="border-b border-border bg-card/40 px-6 py-20 lg:px-8 lg:py-28">
      <div className="mx-auto max-w-3xl">
        <p className="mb-2 font-mono text-xs uppercase tracking-widest text-primary">
          02 / Architecture
        </p>
        <h2 className="mb-4 text-balance text-3xl font-light lg:text-4xl">
          The diagram is the product.
        </h2>
        <p className="mb-12 text-sm leading-relaxed text-muted-foreground">
          Security Data and ML/Analytics feed the supervisory agent fabric.
          Detect, correlate, and assess produce risk findings and bounded
          recommendations &mdash; but every path terminates in a human decision,
          recorded over the TRUST-SAT integrity foundation.
        </p>

        <div className="flex flex-col items-stretch">
          {ARCHITECTURE_FLOW.map((layer, index) => (
            <div key={layer.label} className="flex flex-col items-center">
              <div className="w-full rounded-xl border border-border bg-card px-6 py-4 text-center shadow-sm">
                <p className="font-mono text-sm font-semibold uppercase tracking-widest text-primary">
                  {layer.label}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">{layer.sub}</p>
              </div>
              {index < ARCHITECTURE_FLOW.length - 1 && (
                <div className="h-8 w-px bg-border" aria-hidden="true" />
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

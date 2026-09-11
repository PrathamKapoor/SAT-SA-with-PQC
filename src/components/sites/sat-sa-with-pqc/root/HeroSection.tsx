import { GITHUB_URL, HERO_STATS } from "@/components/sites/sat-sa-with-pqc/root/content";

export function HeroSection() {
  return (
    <section className="relative isolate overflow-hidden border-b border-border px-6 pt-20 pb-16 lg:px-8 lg:pt-28 lg:pb-24">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_15%_-10%,color-mix(in_oklch,var(--primary)_16%,transparent),transparent_60%)]" />
      <div className="mx-auto grid max-w-6xl grid-cols-1 gap-12 lg:grid-cols-[1.6fr_1fr] lg:items-end">
        <div>
          <p className="mb-6 font-mono text-xs uppercase tracking-[0.22em] text-primary">
            Supervisory Analytics &middot; SIH 26157 &middot; NCIIPC
          </p>
          <h1 className="mb-6 max-w-2xl text-balance text-4xl font-light leading-[1.05] lg:text-6xl">
            Periodic SOC assessments become{" "}
            <span className="font-normal text-primary">supervisory intelligence.</span>
          </h1>
          <p className="max-w-xl text-base leading-relaxed text-muted-foreground">
            SAT-SA turns structured CSE submissions into evidence-backed supervisory
            intelligence. Post-quantum trust. Cryptographically verifiable evidence.
            Air-gapped by design.
          </p>

          <div className="mt-10 flex flex-wrap items-center gap-3">
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center justify-center rounded-full bg-primary px-6 py-3 font-mono text-xs font-semibold uppercase tracking-widest text-primary-foreground transition-opacity hover:opacity-90"
            >
              View repository
            </a>
            <a
              href="#architecture"
              className="inline-flex items-center justify-center rounded-full border border-border px-6 py-3 font-mono text-xs uppercase tracking-widest text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
            >
              Architecture
            </a>
            <a
              href="#trust"
              className="inline-flex items-center justify-center rounded-full border border-border px-6 py-3 font-mono text-xs uppercase tracking-widest text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
            >
              TRUST-SAT
            </a>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-0 border-t border-border">
          {HERO_STATS.map((stat, index) => (
            <div
              key={stat.label}
              className={`flex flex-col gap-1 border-t border-border py-6 ${
                index % 2 === 1 ? "border-l pl-8" : ""
              }`}
            >
              <span className="text-3xl font-light">{stat.value}</span>
              <span className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                {stat.label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

import { STATUS_BADGES } from "@/components/sites/contentarchitecture-dev/root/content";

export function HeroSection() {
  return (
    <section className="relative isolate overflow-hidden bg-background px-6 pt-40 pb-24 lg:px-16 lg:pt-56 lg:pb-32">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_20%_-10%,color-mix(in_oklch,var(--tertiary)_16%,transparent),transparent_60%)]" />
      <div className="mx-auto flex max-w-4xl flex-col items-start">
        <p className="mb-6 font-mono text-xs uppercase tracking-widest text-tertiary">
          Full-stack kit for Next.js and Astro.
        </p>
        <h1 className="mb-8 max-w-3xl text-balance text-5xl font-medium leading-[1.05] lg:text-7xl">
          The stack agents don&apos;t reinvent.
        </h1>

        <div className="mb-10 flex flex-wrap gap-2">
          {STATUS_BADGES.map((badge) => (
            <span
              key={badge}
              className="rounded-full border border-border bg-card px-3 py-1 font-mono text-[11px] uppercase tracking-wide text-muted-foreground"
            >
              {badge}
            </span>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-4">
          <a
            href="#pricing"
            className="inline-flex items-center justify-center rounded-full bg-primary px-6 py-3 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
          >
            Get access
          </a>
          <a
            href="#features"
            className="inline-flex items-center gap-1 text-sm font-medium text-foreground/80 underline decoration-border decoration-dashed underline-offset-4 transition-colors hover:text-tertiary"
          >
            Learn more
          </a>
        </div>
      </div>
    </section>
  );
}

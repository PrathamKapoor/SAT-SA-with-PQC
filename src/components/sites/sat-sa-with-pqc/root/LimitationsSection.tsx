import { LIMITATIONS } from "@/components/sites/sat-sa-with-pqc/root/content";

export function LimitationsSection() {
  return (
    <section className="border-b border-border bg-card/40 px-6 py-20 lg:px-8 lg:py-28">
      <div className="mx-auto max-w-3xl">
        <p className="mb-2 font-mono text-xs uppercase tracking-widest text-primary">
          08 / Limitations
        </p>
        <h2 className="mb-2 text-balance text-3xl font-light lg:text-4xl">
          Honesty discipline.
        </h2>
        <p className="mb-10 text-sm text-muted-foreground">
          What the system does not (yet) claim.
        </p>

        <div className="flex flex-col gap-1">
          {LIMITATIONS.map((item) => (
            <div key={item.title} className="border-l-2 border-destructive/50 py-3 pl-5">
              <p className="text-sm font-medium">{item.title}</p>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{item.detail}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

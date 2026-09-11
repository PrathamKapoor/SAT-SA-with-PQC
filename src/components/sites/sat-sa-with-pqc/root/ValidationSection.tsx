import { VALIDATION_ITEMS } from "@/components/sites/sat-sa-with-pqc/root/content";

export function ValidationSection() {
  return (
    <section id="validation" className="border-b border-border bg-card/40 px-6 py-20 lg:px-8 lg:py-28">
      <div className="mx-auto max-w-3xl">
        <p className="mb-2 font-mono text-xs uppercase tracking-widest text-primary">
          06 / Validation
        </p>
        <h2 className="mb-4 text-balance text-3xl font-light lg:text-4xl">
          Per-layer and composition, never one accuracy number.
        </h2>

        <ul className="mt-10 flex flex-col divide-y divide-border border-t border-border">
          {VALIDATION_ITEMS.map((item) => (
            <li key={item} className="py-5 text-sm leading-relaxed text-muted-foreground">
              {item}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

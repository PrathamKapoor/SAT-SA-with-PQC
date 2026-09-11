import { Check } from "lucide-react";
import {
  PRICING_EDITIONS,
  PRICING_INCLUDES,
} from "@/components/sites/contentarchitecture-dev/root/content";

export function PricingSection() {
  return (
    <section id="pricing" className="bg-background px-6 py-24 lg:px-16 lg:py-32">
      <div className="mx-auto max-w-5xl">
        <div className="mb-16 flex flex-col items-start gap-4">
          <span className="rounded-full border border-tertiary/40 bg-tertiary/10 px-3 py-1 font-mono text-xs uppercase tracking-widest text-tertiary">
            Available now
          </span>
          <h2 className="text-balance text-3xl font-medium leading-tight lg:text-5xl">
            Two editions. One architecture. Lifetime updates.
          </h2>
        </div>

        <div className="mb-16 grid grid-cols-1 gap-6 lg:grid-cols-2">
          {PRICING_EDITIONS.map((edition) => (
            <div
              key={edition.number}
              className="flex flex-col justify-between gap-8 rounded-2xl border border-border p-8"
            >
              <div>
                <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
                  {edition.number} / {edition.eyebrow}
                </span>
                <p className="mt-2 text-sm text-muted-foreground">{edition.sub}</p>
              </div>

              <div className="flex items-baseline gap-3">
                <span className="text-4xl font-medium">{edition.price}</span>
                <span className="text-lg text-muted-foreground line-through">
                  {edition.oldPrice}
                </span>
              </div>

              <a
                href={edition.ctaHref}
                className="inline-flex items-center justify-center rounded-full bg-primary px-6 py-3 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
              >
                Get access
              </a>
            </div>
          ))}
        </div>

        <div className="rounded-2xl bg-card p-8">
          <h3 className="mb-6 font-mono text-xs uppercase tracking-widest text-muted-foreground">
            Every edition includes
          </h3>
          <div className="grid grid-cols-1 gap-x-8 gap-y-3 sm:grid-cols-2">
            {PRICING_INCLUDES.map((item) => (
              <div key={item} className="flex items-center gap-3">
                <Check className="size-4 shrink-0 text-tertiary" />
                <span className="text-sm">{item}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

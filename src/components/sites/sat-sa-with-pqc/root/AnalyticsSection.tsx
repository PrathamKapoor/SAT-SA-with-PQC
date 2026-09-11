import {
  ANALYTICS_GROUPS,
  RECOMMENDATION_ACTIONS,
  RISK_DIMENSIONS,
} from "@/components/sites/sat-sa-with-pqc/root/content";

export function AnalyticsSection() {
  return (
    <section id="analytics" className="border-b border-border bg-card/40 px-6 py-20 lg:px-8 lg:py-28">
      <div className="mx-auto max-w-5xl">
        <p className="mb-2 font-mono text-xs uppercase tracking-widest text-primary">
          04 / ML &amp; analytics layer
        </p>
        <h2 className="mb-4 text-balance text-3xl font-light lg:text-4xl">
          Statistics where they&apos;re valid. ML where it adds value.
        </h2>
        <p className="mb-12 max-w-2xl text-sm leading-relaxed text-muted-foreground">
          14 analytical workers run in the default pass, feeding a
          7-dimension decomposable risk score, lexicographic prioritization,
          and a bounded recommendation engine.
        </p>

        <div className="mb-12 grid grid-cols-1 gap-6 lg:grid-cols-2">
          {ANALYTICS_GROUPS.map((group) => (
            <div key={group.title} className="rounded-2xl border border-border bg-card p-6">
              <h3 className="mb-4 font-mono text-xs uppercase tracking-widest text-muted-foreground">
                {group.title}
              </h3>
              <ul className="flex flex-col gap-2">
                {group.items.map((item) => (
                  <li key={item} className="text-sm text-foreground/90">
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div>
            <h3 className="mb-4 font-mono text-xs uppercase tracking-widest text-muted-foreground">
              7-dimension risk
            </h3>
            <div className="flex flex-wrap gap-2">
              {RISK_DIMENSIONS.map((dim) => (
                <span
                  key={dim}
                  className="rounded-full border border-primary/40 bg-primary/10 px-2.5 py-1 font-mono text-[10px] text-primary"
                >
                  {dim}
                </span>
              ))}
            </div>
          </div>
          <div>
            <h3 className="mb-4 font-mono text-xs uppercase tracking-widest text-muted-foreground">
              Recommendation vocabulary
            </h3>
            <div className="flex flex-wrap gap-2">
              {RECOMMENDATION_ACTIONS.map((action) => (
                <span
                  key={action}
                  className="rounded-full border border-border/60 px-2.5 py-1 font-mono text-[10px] text-muted-foreground"
                >
                  {action}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

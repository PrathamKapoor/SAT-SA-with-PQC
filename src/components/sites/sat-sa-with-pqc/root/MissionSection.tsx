import { Check, X } from "lucide-react";
import { MISSION_IS, MISSION_IS_NOT } from "@/components/sites/sat-sa-with-pqc/root/content";

export function MissionSection() {
  return (
    <section className="border-b border-border px-6 py-20 lg:px-8 lg:py-28">
      <div className="mx-auto max-w-5xl">
        <p className="mb-2 font-mono text-xs uppercase tracking-widest text-primary">
          01 / What this is &mdash; and is not
        </p>
        <h2 className="mb-12 text-balance text-3xl font-light lg:text-4xl">
          A human-supervised instrument, not an autonomous authority.
        </h2>

        <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
          <div className="rounded-2xl border border-border bg-card p-6">
            <h3 className="mb-4 font-mono text-xs uppercase tracking-widest text-muted-foreground">
              SAT-SA is
            </h3>
            <ul className="flex flex-col gap-3">
              {MISSION_IS.map((item) => (
                <li key={item} className="flex gap-3 text-sm leading-relaxed">
                  <Check className="mt-0.5 size-4 shrink-0 text-primary" />
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-2xl border border-border bg-card p-6">
            <h3 className="mb-4 font-mono text-xs uppercase tracking-widest text-muted-foreground">
              SAT-SA is not
            </h3>
            <ul className="flex flex-col gap-3">
              {MISSION_IS_NOT.map((item) => (
                <li key={item} className="flex gap-3 text-sm leading-relaxed text-muted-foreground">
                  <X className="mt-0.5 size-4 shrink-0 text-destructive" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}

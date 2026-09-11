import { PROBLEMS, PROBLEMS_INTRO } from "@/components/sites/contentarchitecture-dev/root/content";

export function ProblemsSection() {
  return (
    <section className="bg-background px-6 py-24 lg:px-16 lg:py-32">
      <div className="mx-auto max-w-5xl">
        <div className="mb-16 grid grid-cols-1 gap-8 lg:grid-cols-12">
          <h2 className="text-balance text-3xl font-medium leading-tight lg:col-span-7 lg:text-5xl">
            The page builder alone costs you days. Every single time.
          </h2>
          <p className="text-base leading-relaxed text-muted-foreground lg:col-span-5">
            {PROBLEMS_INTRO}
          </p>
        </div>

        <div className="divide-y divide-border rounded-2xl border border-border">
          {PROBLEMS.map((problem) => (
            <div
              key={problem.number}
              className="flex items-center justify-between gap-6 px-6 py-4"
            >
              <div className="flex min-w-0 items-center gap-4">
                <span className="font-mono text-xs text-tertiary">{problem.number}</span>
                <span className="truncate text-sm font-medium lg:text-base">{problem.title}</span>
              </div>
              <span className="shrink-0 font-mono text-xs text-muted-foreground lg:text-sm">
                {problem.time}
              </span>
            </div>
          ))}
        </div>

        <p className="mt-8 text-center font-mono text-xs uppercase tracking-widest text-muted-foreground">
          Estimated time lost: ~24 hours per project (3 full days)
        </p>
      </div>
    </section>
  );
}

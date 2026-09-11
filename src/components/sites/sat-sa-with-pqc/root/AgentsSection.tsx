import {
  AGENT_CONTRACT,
  AGENT_GROUPS,
  DECISION_VOCABULARIES,
  SUPERVISOR_ENGINE,
} from "@/components/sites/sat-sa-with-pqc/root/content";

export function AgentsSection() {
  return (
    <section id="agents" className="border-b border-border px-6 py-20 lg:px-8 lg:py-28">
      <div className="mx-auto max-w-5xl">
        <p className="mb-2 font-mono text-xs uppercase tracking-widest text-primary">
          03 / The 26-agent model
        </p>
        <h2 className="mb-4 text-balance text-3xl font-light lg:text-4xl">
          Responsibility separation, not a target.
        </h2>
        <p className="mb-6 max-w-2xl text-sm leading-relaxed text-muted-foreground">
          {AGENT_CONTRACT} Agents must not make irreversible supervisory
          decisions independently.
        </p>
        <p className="mb-12 max-w-2xl text-sm leading-relaxed text-muted-foreground">
          {SUPERVISOR_ENGINE}
        </p>

        <div className="mb-16 grid grid-cols-1 gap-8 lg:grid-cols-2">
          {AGENT_GROUPS.map((group) => (
            <div key={group.family} className="rounded-2xl border border-border bg-card p-6">
              <div className="mb-4 flex items-baseline justify-between gap-2">
                <h3 className="font-mono text-sm uppercase tracking-widest text-primary">
                  {group.family}
                </h3>
                <span className="font-mono text-xs text-muted-foreground">
                  {group.count} agents
                </span>
              </div>
              <p className="mb-4 text-xs leading-relaxed text-muted-foreground">
                {group.description}
              </p>
              <ul className="flex flex-col divide-y divide-border">
                {group.agents.map((agent) => (
                  <li key={agent} className="py-2 font-mono text-xs">
                    {agent}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {DECISION_VOCABULARIES.map((vocab) => (
            <div key={vocab.name} className="rounded-2xl border border-border p-6">
              <p className="mb-1 font-mono text-xs uppercase tracking-widest text-primary">
                {vocab.name} vocabulary
              </p>
              <p className="mb-4 text-xs text-muted-foreground">{vocab.note}</p>
              <div className="flex flex-wrap gap-2">
                {vocab.actions.map((action) => (
                  <span
                    key={action}
                    className="rounded-full border border-border/60 px-2.5 py-1 font-mono text-[10px] text-muted-foreground"
                  >
                    {action}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

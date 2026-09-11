import { Folder, GitBranch } from "lucide-react";
import {
  DEMO_STEPS,
  GITHUB_URL,
  INSTALL_STEPS,
  REPO_TREE,
} from "@/components/sites/sat-sa-with-pqc/root/content";

export function RepoSection() {
  return (
    <section id="repo" className="border-b border-border px-6 py-20 lg:px-8 lg:py-28">
      <div className="mx-auto max-w-5xl">
        <p className="mb-2 font-mono text-xs uppercase tracking-widest text-primary">
          07 / Repository
        </p>
        <h2 className="mb-4 text-balance text-3xl font-light lg:text-4xl">
          Offline / air-gapped install.
        </h2>
        <div className="mb-10 flex items-center gap-3 font-mono text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <GitBranch className="size-3.5" /> main
          </span>
          <span className="h-3 w-px bg-border" />
          <a href={GITHUB_URL} target="_blank" rel="noreferrer" className="hover:text-foreground">
            github.com/PrathamKapoor/SAT-SA-with-PQC
          </a>
        </div>

        <div className="grid grid-cols-1 gap-6 overflow-hidden rounded-2xl border border-border bg-card lg:grid-cols-12">
          <div className="p-6 lg:col-span-5 lg:border-r lg:border-border">
            <h3 className="mb-4 font-mono text-xs uppercase tracking-widest text-muted-foreground">
              Project structure
            </h3>
            <ul className="flex flex-col gap-0.5 font-mono text-xs text-muted-foreground">
              {REPO_TREE.map((entry) => (
                <li key={entry.name} className="flex items-start gap-2 rounded px-2 py-1.5">
                  <Folder className="mt-0.5 size-3.5 shrink-0 text-primary" />
                  <span>
                    <span className="text-foreground">{entry.name}</span>{" "}
                    <span className="text-muted-foreground/80">{entry.note}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div className="p-6 lg:col-span-7">
            <h3 className="mb-3 font-mono text-xs uppercase tracking-widest text-muted-foreground">
              Install
            </h3>
            <pre className="mb-6 overflow-x-auto rounded-lg bg-background p-4 font-mono text-xs leading-relaxed text-foreground/90">
              {INSTALL_STEPS.join("\n")}
            </pre>
            <h3 className="mb-3 font-mono text-xs uppercase tracking-widest text-muted-foreground">
              Demo (the judge path)
            </h3>
            <pre className="overflow-x-auto rounded-lg bg-background p-4 font-mono text-xs leading-relaxed text-foreground/90">
              {DEMO_STEPS.join("\n")}
            </pre>
          </div>
        </div>
      </div>
    </section>
  );
}

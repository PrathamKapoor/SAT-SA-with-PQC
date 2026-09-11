import { GitBranch, FileText, Folder } from "lucide-react";
import { README_EXCERPT, REPO_TREE } from "@/components/sites/contentarchitecture-dev/root/content";

const FOLDER_NAMES = new Set([
  ".agents",
  ".zed",
  "app",
  "(web)",
  "api",
  "sanity-studio",
  "components",
  "docs",
  "features",
  "agents",
  "auth",
  "blog",
  "dom",
  "draft-mode",
  "fonts",
  "forms",
  "legal",
  "motion",
  "mux",
  "page-builder",
  "rich-text",
  "sanity",
  "site",
  "spam-prevention",
  "style",
  "umami",
  "utils",
  "view-transition",
  "public",
  "scripts",
  "seed",
  "templates",
]);

export function RepoSection() {
  return (
    <section id="the-repo" className="bg-background px-6 py-24 lg:px-16 lg:py-32">
      <div className="mx-auto max-w-5xl">
        <h2 className="mb-4 text-balance text-3xl font-medium leading-tight lg:text-5xl">
          This is the actual repo.
        </h2>
        <div className="mb-10 flex items-center gap-3 font-mono text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <GitBranch className="size-3.5" /> main
          </span>
          <span className="h-3 w-px bg-border" />
          <span>Updated today</span>
          <span className="h-3 w-px bg-border" />
          <span>162 commits</span>
        </div>

        <div className="grid grid-cols-1 gap-6 overflow-hidden rounded-2xl border border-border bg-card lg:grid-cols-12">
          <div className="max-h-[28rem] overflow-y-auto border-border p-4 lg:col-span-5 lg:border-r">
            <ul className="flex flex-col gap-0.5 font-mono text-xs text-muted-foreground">
              {REPO_TREE.map((entry) => (
                <li
                  key={entry}
                  className="flex items-center gap-2 rounded px-2 py-1 hover:bg-accent hover:text-foreground"
                >
                  {FOLDER_NAMES.has(entry) ? (
                    <Folder className="size-3.5 shrink-0 text-tertiary" />
                  ) : (
                    <FileText className="size-3.5 shrink-0" />
                  )}
                  <span className="truncate">{entry}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="p-6 lg:col-span-7">
            <h3 className="mb-3 font-mono text-sm font-medium"># {README_EXCERPT.title}</h3>
            <p className="mb-6 text-sm leading-relaxed text-muted-foreground">
              {README_EXCERPT.intro}
            </p>
            <h4 className="mb-3 text-sm font-medium">Features</h4>
            <ul className="flex flex-col gap-2">
              {README_EXCERPT.features.map((feature) => (
                <li
                  key={feature}
                  className="flex gap-2 text-sm leading-relaxed text-muted-foreground"
                >
                  <span className="mt-2 size-1 shrink-0 rounded-full bg-tertiary" />
                  {feature}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}

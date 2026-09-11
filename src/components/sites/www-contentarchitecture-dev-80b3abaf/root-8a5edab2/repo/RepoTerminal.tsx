"use client";

import type { RepoCta, RepoEdition, RepoFileNode, RepoFolderNode } from "./model";

export interface RepoTerminalProps {
  /** Root name + repo stats (git chart). */
  edition: RepoEdition;
  /** Current tree (includes files added by plop). */
  tree: RepoFolderNode;
  /** Pinned "get-access" line. */
  cta: RepoCta;
  /** Input placeholder before the first command (CA "try: git, ls, tree, plop, cat README.md"). */
  placeholder: string;
  /** Header label ("Terminal"). */
  title: string;
  /** Run `command` whenever `id` changes (footer commits button → "git"). */
  request?: { id: number; command: string };
  onOpenFile: (path: string) => void;
  onAddFile: (folderPath: string, file: RepoFileNode) => void;
}

/** STUB — replaced by the RepoTerminal builder (B7c). */
export function RepoTerminal({ title, placeholder }: RepoTerminalProps) {
  return (
    <section aria-label="Terminal" className="flex h-full min-h-0 flex-col">
      <div className="shrink-0 border-white/10 border-b px-16 py-8 font-mono text-caption-10 text-white/40 uppercase tracking-wide">
        {title}
      </div>
      <div className="min-h-0 flex-1 px-16 py-10 font-mono text-caption-10 text-white/25">{placeholder}</div>
    </section>
  );
}

"use client";

import type { RepoFolderNode } from "./model";

export interface RepoFileTreeProps {
  /** Edition root; its children are rendered (the root row itself is not shown). */
  tree: RepoFolderNode;
  /** Repo-relative folder paths that are expanded. */
  openPaths: ReadonlySet<string>;
  /** Repo-relative path of the file open in the editor. */
  activePath: string;
  onToggleFolder: (path: string) => void;
  onOpenFile: (path: string) => void;
}

/** STUB — replaced by the RepoFileTree builder (B7a). */
export function RepoFileTree({ tree }: RepoFileTreeProps) {
  return (
    <nav aria-label="File explorer" className="flex min-h-0 flex-1 flex-col justify-between gap-16">
      <div className="min-h-0 flex-1 overflow-auto py-12 font-mono text-caption-10 uppercase text-white/55">
        {tree.children.length} items
      </div>
    </nav>
  );
}

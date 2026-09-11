"use client";

export interface RepoEditorProps {
  /** Repo-relative path of the open file ("README.md"). */
  path: string;
  /** File contents (controlled). */
  value: string;
  /** Edits are kept by the parent per path. */
  onChange: (value: string) => void;
}

/** STUB — replaced by the RepoEditor builder (B7b). */
export function RepoEditor({ path, value, onChange }: RepoEditorProps) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="shrink-0 border-white/10 border-b px-16 py-10 font-mono text-caption-10 text-white/40 uppercase tracking-wide">
        {path}
      </div>
      <textarea
        aria-label={`${path} contents`}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-0 flex-1 resize-none bg-transparent p-16 font-mono text-caption-10 text-ghost-grey outline-none"
      />
    </div>
  );
}

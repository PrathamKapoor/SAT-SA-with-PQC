"use client";

import { useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { cn } from "@/lib/utils";
import {
  CodeFileIcon,
  ComponentFileIcon,
  ConfigFileIcon,
  CssFileIcon,
  FileIcon,
  ImageFileIcon,
  JsonFileIcon,
  TextFileIcon,
} from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/icons";
import { fileIconKind, parentPath, walkFiles, type RepoFileNode, type RepoFolderNode } from "./model";

export interface RepoSearchProps {
  /** Current edition tree (includes files added by plop). */
  tree: RepoFolderNode;
  /** Root folder name, shown as the path prefix of every result. */
  rootName: string;
  /** Input placeholder ("Search project files..."). */
  placeholder: string;
  /** Input aria-label ("Search files"). */
  label: string;
  onSelect: (path: string) => void;
  onClose: () => void;
}

interface FileEntry {
  path: string;
  node: RepoFileNode;
}

const MAX_RESULTS = 60;

/** Empty query: every file in tree order. Otherwise name prefix, then name includes, then path includes. */
function rankFiles(files: FileEntry[], query: string): FileEntry[] {
  const q = query.trim().toLowerCase();
  if (!q) return files;
  const prefix: FileEntry[] = [];
  const nameMatch: FileEntry[] = [];
  const pathMatch: FileEntry[] = [];
  for (const file of files) {
    const name = file.node.name.toLowerCase();
    if (name.startsWith(q)) prefix.push(file);
    else if (name.includes(q)) nameMatch.push(file);
    else if (file.path.toLowerCase().includes(q)) pathMatch.push(file);
  }
  return [...prefix, ...nameMatch, ...pathMatch].slice(0, MAX_RESULTS);
}

function FileKindIcon({ name, className }: { name: string; className?: string }) {
  switch (fileIconKind(name)) {
    case "component":
      return <ComponentFileIcon aria-hidden="true" className={className} />;
    case "code":
      return <CodeFileIcon aria-hidden="true" className={className} />;
    case "json":
      return <JsonFileIcon aria-hidden="true" className={className} />;
    case "css":
      return <CssFileIcon aria-hidden="true" className={className} />;
    case "image":
      return <ImageFileIcon aria-hidden="true" className={className} />;
    case "config":
      return <ConfigFileIcon aria-hidden="true" className={className} />;
    case "text":
      return <TextFileIcon aria-hidden="true" className={className} />;
    default:
      return <FileIcon aria-hidden="true" className={className} />;
  }
}

/** Ctrl/⌘ K file palette, rendered as an overlay inside the IDE window. */
export function RepoSearch({ tree, rootName, placeholder, label, onSelect, onClose }: RepoSearchProps) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const files = useMemo(() => walkFiles(tree), [tree]);
  const results = useMemo(() => rankFiles(files, query), [files, query]);
  const current = Math.min(selected, results.length - 1);

  useEffect(() => {
    inputRef.current?.focus({ preventScroll: true });
  }, []);

  useEffect(() => {
    if (current < 0) return;
    listRef.current?.children[current]?.scrollIntoView({ block: "nearest" });
  }, [current]);

  const onKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        setSelected(Math.min(current + 1, results.length - 1));
        break;
      case "ArrowUp":
        event.preventDefault();
        setSelected(Math.max(current - 1, 0));
        break;
      case "Enter": {
        const result = results[current];
        if (!result) return;
        event.preventDefault();
        onSelect(result.path);
        break;
      }
      case "Escape":
        event.preventDefault();
        event.stopPropagation();
        onClose();
        break;
    }
  };

  return (
    <div className="absolute inset-0 z-3 flex items-start justify-center" onKeyDown={onKeyDown}>
      <div
        aria-hidden="true"
        onClick={onClose}
        className="absolute inset-0 bg-black-deep/50 transition-opacity duration-150 ease-out starting:opacity-0 motion-reduce:transition-none"
      />
      <div className="relative mt-10 flex max-h-[min(70%,440px)] w-[min(92%,560px)] flex-col overflow-hidden rounded-8 bg-black shadow-2xl ring-1 ring-white/15 transition duration-150 ease-out starting:-translate-y-4 starting:scale-98 starting:opacity-0 motion-reduce:transition-none">
        <input
          ref={inputRef}
          type="text"
          aria-label={label}
          placeholder={placeholder}
          spellCheck={false}
          autoComplete="off"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setSelected(0);
          }}
          className="shrink-0 border-white/10 border-b bg-transparent px-16 py-12 font-mono text-caption-10 text-white caret-accent outline-none placeholder:text-white/30"
        />
        <div ref={listRef} data-lenis-prevent="" className="scrollbar-thin min-h-0 flex-1 overflow-y-auto py-6">
          {results.map((result, index) => {
            const parent = parentPath(result.path);
            return (
              <button
                key={result.path}
                type="button"
                onClick={() => onSelect(result.path)}
                className={cn(
                  "flex w-full cursor-pointer items-center gap-10 px-16 py-6 text-left font-mono text-caption-10",
                  index === current ? "bg-white/10" : "hover:bg-white/[0.04]",
                )}
              >
                <FileKindIcon name={result.node.name} className="size-[1.05em] shrink-0 text-white/50" />
                <span className="shrink-0 text-white/90">{result.node.name}</span>
                <span className="truncate text-white/35">{parent ? `${rootName}/${parent}/` : `${rootName}/`}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

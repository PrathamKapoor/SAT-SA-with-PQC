"use client";

import { useEffect, useRef, useState, type ComponentType, type KeyboardEvent, type SVGProps } from "react";

import { cn } from "@/lib/utils";
import { usePrefersReducedMotion } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/hooks";
import {
  ChevronRightIcon,
  CodeFileIcon,
  ComponentFileIcon,
  ConfigFileIcon,
  CssFileIcon,
  FileIcon,
  FolderIcon,
  FolderOpenIcon,
  ImageFileIcon,
  JsonFileIcon,
  TextFileIcon,
} from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/icons";

import { fileIconKind, joinPath, parentPath, type FileIconKind, type RepoFileNode, type RepoFolderNode } from "./model";

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

const FILE_ICONS: Record<FileIconKind, ComponentType<SVGProps<SVGSVGElement>>> = {
  component: ComponentFileIcon,
  code: CodeFileIcon,
  json: JsonFileIcon,
  css: CssFileIcon,
  image: ImageFileIcon,
  config: ConfigFileIcon,
  text: TextFileIcon,
  file: FileIcon,
};

const ROW_BASE =
  "flex w-full items-center gap-6 py-3 pr-10 text-left font-mono text-caption-10 uppercase tracking-wide outline-none transition-colors duration-100 cursor-pointer";

/** Matches the children wrapper's `duration-200` grid-rows transition (+ a frame of slack). */
const EXPAND_DURATION_MS = 220;

function rowIndent(depth: number) {
  return { paddingLeft: 10 + depth * 14 };
}

/** "a/b/c.tsx" → ["a", "a/b"]. */
function ancestorPaths(path: string): string[] {
  const out: string[] = [];
  for (let parent = parentPath(path); parent !== ""; parent = parentPath(parent)) out.push(parent);
  return out;
}

/** Rows that are currently reachable (not inside a collapsed, `inert` folder). */
function visibleRows(container: HTMLElement): HTMLButtonElement[] {
  return Array.from(container.querySelectorAll<HTMLButtonElement>("button[data-path]")).filter(
    (row) => !row.closest("[inert]"),
  );
}

/** `block: "nearest"` scrolling, restricted to the explorer's own scroll container. */
function scrollRowIntoView(container: HTMLElement, row: HTMLElement) {
  const box = container.getBoundingClientRect();
  const rect = row.getBoundingClientRect();
  const top = box.top + container.clientTop;
  const bottom = top + container.clientHeight;
  if (rect.top < top) container.scrollTop += rect.top - top;
  else if (rect.bottom > bottom) container.scrollTop += rect.bottom - bottom;
}

interface TreeState {
  openPaths: ReadonlySet<string>;
  activePath: string;
  onToggleFolder: (path: string) => void;
  onOpenFile: (path: string) => void;
}

interface TreeListProps {
  folder: RepoFolderNode;
  base: string;
  depth: number;
  state: TreeState;
  className?: string;
}

function TreeList({ folder, base, depth, state, className }: TreeListProps) {
  return (
    <ul className={className}>
      {folder.children.map((child) => {
        const path = joinPath(base, child.name);
        return child.type === "folder" ? (
          <FolderItem key={`d:${child.name}`} node={child} path={path} depth={depth} state={state} />
        ) : (
          <FileItem key={`f:${child.name}`} node={child} path={path} depth={depth} state={state} />
        );
      })}
    </ul>
  );
}

interface FolderItemProps {
  node: RepoFolderNode;
  path: string;
  depth: number;
  state: TreeState;
}

function FolderItem({ node, path, depth, state }: FolderItemProps) {
  const open = state.openPaths.has(path);
  // Children mount lazily on first open, then stay mounted so the close animation can play.
  const [rendered, setRendered] = useState(open);
  if (open && !rendered) setRendered(true);

  return (
    <li>
      <button
        type="button"
        aria-expanded={open}
        data-path={path}
        style={rowIndent(depth)}
        className={cn(ROW_BASE, "text-white/60 hover:bg-white/[0.04] hover:text-white/90")}
        onClick={() => state.onToggleFolder(path)}
      >
        <ChevronRightIcon
          className={cn(
            "size-[0.85em] shrink-0 opacity-50 transition-transform duration-200 ease-out motion-reduce:transition-none",
            open && "rotate-90",
          )}
        />
        {open ? (
          <FolderOpenIcon className="size-[1.05em] shrink-0" />
        ) : (
          <FolderIcon className="size-[1.05em] shrink-0" />
        )}
        <span className="whitespace-nowrap">{node.name}</span>
      </button>
      <div
        className="grid transition-[grid-template-rows] duration-200 ease-out motion-reduce:transition-none"
        style={{ gridTemplateRows: open ? "1fr" : "0fr" }}
      >
        <div className="overflow-hidden" inert={!open}>
          {rendered ? <TreeList folder={node} base={path} depth={depth + 1} state={state} /> : null}
        </div>
      </div>
    </li>
  );
}

interface FileItemProps {
  node: RepoFileNode;
  path: string;
  depth: number;
  state: TreeState;
}

function FileItem({ node, path, depth, state }: FileItemProps) {
  const active = state.activePath === path;
  const Icon = FILE_ICONS[fileIconKind(node.name)];

  return (
    <li>
      <button
        type="button"
        aria-current={active ? "true" : undefined}
        data-path={path}
        style={rowIndent(depth)}
        className={cn(
          ROW_BASE,
          active ? "bg-white/[0.06] text-white" : "text-white/55 hover:bg-white/[0.04] hover:text-white/90",
        )}
        onClick={() => state.onOpenFile(path)}
      >
        <span className="size-[0.85em] shrink-0" aria-hidden="true" />
        <Icon className="size-[1.05em] shrink-0 text-current/70" />
        <span className="whitespace-nowrap">{node.name}</span>
      </button>
    </li>
  );
}

export function RepoFileTree({ tree, openPaths, activePath, onToggleFolder, onOpenFile }: RepoFileTreeProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const reducedMotion = usePrefersReducedMotion();
  const prevActiveRef = useRef(activePath);
  const prevOpenRef = useRef(openPaths);
  const pendingScrollRef = useRef(false);

  // Reveal the active row when it changes from outside (search palette, `open`, plop). The parent
  // opens the ancestors; if any of them just started expanding, wait for the grid animation so the
  // row is measured at its final position.
  useEffect(() => {
    const prevOpen = prevOpenRef.current;
    prevOpenRef.current = openPaths;
    if (activePath !== prevActiveRef.current) {
      prevActiveRef.current = activePath;
      pendingScrollRef.current = true;
    }
    if (!pendingScrollRef.current) return;

    const expanding = !reducedMotion && ancestorPaths(activePath).some((p) => openPaths.has(p) && !prevOpen.has(p));
    const reveal = () => {
      pendingScrollRef.current = false;
      const container = scrollRef.current;
      const row = container?.querySelector<HTMLElement>('button[aria-current="true"]');
      if (container && row && !row.closest("[inert]")) scrollRowIntoView(container, row);
    };

    if (expanding) {
      const timer = window.setTimeout(reveal, EXPAND_DURATION_MS);
      return () => window.clearTimeout(timer);
    }
    const frame = window.requestAnimationFrame(reveal);
    return () => window.cancelAnimationFrame(frame);
  }, [activePath, openPaths, reducedMotion]);

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    const row = event.target;
    if (!(row instanceof HTMLButtonElement) || row.dataset.path === undefined) return;

    const rows = visibleRows(event.currentTarget);
    const index = rows.indexOf(row);
    if (index < 0) return;
    const path = row.dataset.path;
    const isFolder = row.hasAttribute("aria-expanded");
    const expanded = row.getAttribute("aria-expanded") === "true";

    let handled = true;
    switch (event.key) {
      case "ArrowDown":
        rows[index + 1]?.focus();
        break;
      case "ArrowUp":
        rows[index - 1]?.focus();
        break;
      case "Home":
        rows[0]?.focus();
        break;
      case "End":
        rows[rows.length - 1]?.focus();
        break;
      case "ArrowRight":
        if (!isFolder) {
          handled = false;
          break;
        }
        if (!expanded) onToggleFolder(path);
        else if (rows[index + 1]?.dataset.path?.startsWith(`${path}/`)) rows[index + 1].focus();
        break;
      case "ArrowLeft": {
        if (isFolder && expanded) {
          onToggleFolder(path);
          break;
        }
        const parent = parentPath(path);
        if (parent) rows.find((candidate) => candidate.dataset.path === parent)?.focus();
        break;
      }
      default:
        handled = false;
    }
    if (handled) event.preventDefault();
  };

  const state: TreeState = { openPaths, activePath, onToggleFolder, onOpenFile };

  return (
    <nav aria-label="File explorer" className="flex min-h-0 flex-1 flex-col justify-between gap-16">
      <div
        ref={scrollRef}
        className="scrollbar-thin min-h-0 flex-1 overflow-auto py-12"
        data-lenis-prevent
        onKeyDown={handleKeyDown}
      >
        <TreeList folder={tree} base="" depth={0} state={state} className="w-max min-w-full" />
      </div>
    </nav>
  );
}

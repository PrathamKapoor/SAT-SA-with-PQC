"use client";

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { cn } from "@/lib/utils";
import { useInView } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/hooks";
import { CommitsIcon, SearchIcon, TerminalIcon } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/icons";
import {
  addFile,
  defaultActivePath,
  defaultOpenPaths,
  getNode,
  parentPath,
  type RepoCta,
  type RepoEdition,
  type RepoFileNode,
} from "./repo/model";
import { RepoEditor } from "./repo/RepoEditor";
import { RepoFileTree } from "./repo/RepoFileTree";
import { RepoSearch } from "./repo/RepoSearch";
import { RepoTerminal } from "./repo/RepoTerminal";

export interface RepoEditionContent extends RepoEdition {
  /** Pinned terminal line for this edition (label, price note, link). */
  cta: RepoCta;
}

export interface RepoContent {
  /** Section anchor id ("the-repo"). */
  id: string;
  /** Centred header label ("This is the actual repo."). */
  title: string;
  /** Terminal header label ("Terminal"). */
  terminalTitle: string;
  /** Terminal input placeholder ("try: git, ls, tree, plop, cat README.md"). */
  terminalHint: string;
  /** One header tab per edition; the first one is active on load. */
  editions: RepoEditionContent[];
  labels: {
    hideTerminal: string;
    showTerminal: string;
    search: string;
    searchPlaceholder: string;
    /** aria-label of the palette input (CA: "Search project files"). */
    searchInput: string;
    resizeExplorer: string;
    resizeTerminal: string;
    resizeBoth: string;
    commitGraphTitle: string;
    commitGraphLabel: string;
    commits: string;
  };
}

type RepoRequest = { id: number; command: string };
type DragAxis = "x" | "y" | "xy";

const EXPLORER_DEFAULT = 240;
const EXPLORER_MIN = 140;
const EXPLORER_MAX_RATIO = 0.6;
const TERMINAL_DEFAULT = 200;
const TERMINAL_MIN = 72;
const TERMINAL_MAX_RATIO = 0.7;
const KEY_STEP = 16;
const DRAG_CURSORS: Record<DragAxis, string> = { x: "col-resize", y: "row-resize", xy: "nesw-resize" };

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(value, max));
}

/** Every ancestor folder of a repo-relative path ("a/b/c.ts" → "a", "a/b"). */
function ancestorPaths(path: string): string[] {
  const out: string[] = [];
  for (let parent = parentPath(path); parent !== ""; parent = parentPath(parent)) out.push(parent);
  return out;
}

const subscribeNoop = () => () => {};
const getModifierLabel = () => (/Mac|iPhone|iPad/.test(navigator.platform) ? "⌘" : "Ctrl");
const getServerModifierLabel = () => "Ctrl";

export function RepoSection({ content }: { content: RepoContent }) {
  const { labels } = content;
  const firstEdition = content.editions[0];

  const [editionIndex, setEditionIndex] = useState(0);
  const edition = content.editions[editionIndex] ?? firstEdition;

  const [tree, setTree] = useState(() => firstEdition.tree);
  const [openPaths, setOpenPaths] = useState<ReadonlySet<string>>(() => defaultOpenPaths(firstEdition.tree));
  const [activePath, setActivePath] = useState(() => defaultActivePath(firstEdition.tree));
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [terminalOpen, setTerminalOpen] = useState(true);
  const [explorerW, setExplorerW] = useState(EXPLORER_DEFAULT);
  const [terminalH, setTerminalH] = useState(TERMINAL_DEFAULT);
  const [searchOpen, setSearchOpen] = useState(false);
  const [request, setRequest] = useState<RepoRequest | undefined>(undefined);

  const mod = useSyncExternalStore(subscribeNoop, getModifierLabel, getServerModifierLabel);

  const sectionRef = useRef<HTMLDivElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const tabGroupRef = useRef<HTMLDivElement>(null);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const dragRef = useRef<DragAxis | null>(null);

  // ── Active edition pill: one span that slides to the active tab ──────────────────────────────
  const [pill, setPill] = useState<{ x: number; width: number } | null>(null);

  useLayoutEffect(() => {
    const group = tabGroupRef.current;
    if (!group) return;
    const measure = () => {
      const button = tabRefs.current[editionIndex];
      if (!button) return;
      const next = { x: button.offsetLeft, width: button.offsetWidth };
      setPill((prev) => (prev && prev.x === next.x && prev.width === next.width ? prev : next));
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(group);
    for (const button of tabRefs.current) if (button) observer.observe(button);
    window.addEventListener("resize", measure);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [editionIndex, content.editions.length]);

  // ── Edition / file state ──────────────────────────────────────────────────────────────────────
  const switchEdition = (index: number) => {
    const next = content.editions[index];
    if (!next || index === editionIndex) return;
    setEditionIndex(index);
    setTree(next.tree);
    setOpenPaths(defaultOpenPaths(next.tree));
    setActivePath(defaultActivePath(next.tree));
    setEdits({});
    setRequest(undefined);
  };

  const openFile = useCallback((path: string) => {
    setActivePath(path);
    setOpenPaths((prev) => {
      const missing = ancestorPaths(path).filter((folder) => !prev.has(folder));
      if (missing.length === 0) return prev;
      const next = new Set(prev);
      for (const folder of missing) next.add(folder);
      return next;
    });
  }, []);

  const toggleFolder = useCallback((path: string) => {
    setOpenPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }, []);

  const onAddFile = useCallback((folderPath: string, file: RepoFileNode) => {
    setTree((prev) => addFile(prev, folderPath, file));
    // A re-plopped file replaces its predecessor, so drop any stale edits for that path.
    const path = folderPath ? `${folderPath}/${file.name}` : file.name;
    setEdits((prev) => {
      if (!(path in prev)) return prev;
      const next = { ...prev };
      delete next[path];
      return next;
    });
  }, []);

  const activeNode = getNode(tree, activePath);
  const editorValue = edits[activePath] ?? (activeNode?.type === "file" ? activeNode.content : "");

  const onEditorChange = useCallback(
    (value: string) => setEdits((prev) => ({ ...prev, [activePath]: value })),
    [activePath],
  );

  const showCommitGraph = () => {
    setTerminalOpen(true);
    setRequest((prev) => ({ id: (prev?.id ?? 0) + 1, command: "git" }));
  };

  const onSearchSelect = useCallback(
    (path: string) => {
      openFile(path);
      setSearchOpen(false);
    },
    [openFile],
  );
  const closeSearch = useCallback(() => setSearchOpen(false), []);

  // ── Shortcuts (only while the section is at least 30% in view) ───────────────────────────────
  const inView = useInView(sectionRef, { threshold: 0.3, once: false });

  useEffect(() => {
    if (!inView) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (!(event.metaKey || event.ctrlKey) || event.altKey || event.shiftKey) return;
      const key = event.key.toLowerCase();
      if (key === "j") {
        event.preventDefault();
        setTerminalOpen((open) => !open);
      } else if (key === "k") {
        event.preventDefault();
        setSearchOpen(true);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [inView]);

  // ── Resizers ──────────────────────────────────────────────────────────────────────────────────
  const resetBodyDragStyles = () => {
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
  };

  useEffect(
    () => () => {
      if (dragRef.current) resetBodyDragStyles();
    },
    [],
  );

  const onResizePointerDown = (axis: DragAxis) => (event: ReactPointerEvent<HTMLButtonElement>) => {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = axis;
    document.body.style.cursor = DRAG_CURSORS[axis];
    document.body.style.userSelect = "none";
  };

  const onResizePointerMove = (event: ReactPointerEvent<HTMLButtonElement>) => {
    const axis = dragRef.current;
    const rect = bodyRef.current?.getBoundingClientRect();
    if (!axis || !rect) return;
    if (axis !== "y") {
      setExplorerW(clamp(event.clientX - rect.left, EXPLORER_MIN, rect.width * EXPLORER_MAX_RATIO));
    }
    if (axis !== "x") {
      setTerminalH(clamp(rect.bottom - event.clientY, TERMINAL_MIN, rect.height * TERMINAL_MAX_RATIO));
    }
  };

  const onResizePointerEnd = (event: ReactPointerEvent<HTMLButtonElement>) => {
    if (!dragRef.current) return;
    dragRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    resetBodyDragStyles();
  };

  const resizeHandlers = (axis: DragAxis) => ({
    onPointerDown: onResizePointerDown(axis),
    onPointerMove: onResizePointerMove,
    onPointerUp: onResizePointerEnd,
    onPointerCancel: onResizePointerEnd,
    onLostPointerCapture: onResizePointerEnd,
  });

  const onExplorerKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>) => {
    const delta = event.key === "ArrowLeft" ? -KEY_STEP : event.key === "ArrowRight" ? KEY_STEP : 0;
    const rect = bodyRef.current?.getBoundingClientRect();
    if (!delta || !rect) return;
    event.preventDefault();
    setExplorerW((width) => clamp(width + delta, EXPLORER_MIN, rect.width * EXPLORER_MAX_RATIO));
  };

  const onTerminalKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>) => {
    const delta = event.key === "ArrowUp" ? KEY_STEP : event.key === "ArrowDown" ? -KEY_STEP : 0;
    const rect = bodyRef.current?.getBoundingClientRect();
    if (!delta || !rect) return;
    event.preventDefault();
    setTerminalH((height) => clamp(height + delta, TERMINAL_MIN, rect.height * TERMINAL_MAX_RATIO));
  };

  const { repo } = edition;

  return (
    <div
      ref={sectionRef}
      id={content.id}
      data-page-builder-section="ideSection"
      className="h-svh bg-off-white px-16 py-72 text-black lg:p-80"
    >
      <div className="h-full w-full">
        <div className="rounded-8 p-6 shadow-lg ring ring-black-deep transition-colors duration-300 lg:p-8 bg-black-deep bg-dither h-full">
          <div className="relative isolate flex h-full flex-col overflow-hidden rounded-4 bg-black text-white ring-1 ring-white/10">
            {/* HEADER */}
            <div className="relative flex h-34 shrink-0 items-center justify-center border-white/10 border-b px-16">
              <div className="absolute top-1/2 left-8 -translate-y-1/2">
                <div ref={tabGroupRef} className="relative isolate flex items-center gap-2 rounded-4 bg-white/5 p-2">
                  {pill ? (
                    <span
                      aria-hidden="true"
                      className="absolute inset-y-2 left-0 rounded-4 bg-white/10 transition-[transform,width] duration-300 ease-[cubic-bezier(0.23,1,0.32,1)] motion-reduce:transition-none"
                      style={{ transform: `translateX(${pill.x}px)`, width: pill.width }}
                    />
                  ) : null}
                  {content.editions.map((ed, index) => {
                    const active = index === editionIndex;
                    return (
                      <button
                        key={ed.id}
                        ref={(node) => {
                          tabRefs.current[index] = node;
                        }}
                        type="button"
                        aria-label={ed.ariaLabel}
                        aria-pressed={active}
                        onClick={() => switchEdition(index)}
                        className={cn(
                          "relative cursor-pointer rounded-4 px-6 py-2 font-mono text-caption-10 uppercase tracking-wide transition-colors",
                          active ? "text-white" : "text-white/40 hover:text-white",
                        )}
                      >
                        <span className="relative">{ed.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
              <span className="max-w-1/3 truncate font-mono text-caption-10 text-white/40 uppercase tracking-wide">
                {content.title}
              </span>
              <div className="absolute top-1/2 right-8 flex -translate-y-1/2 items-center gap-4">
                <button
                  type="button"
                  aria-label={terminalOpen ? labels.hideTerminal : labels.showTerminal}
                  aria-pressed={terminalOpen}
                  onClick={() => setTerminalOpen((open) => !open)}
                  className={cn(
                    "flex cursor-pointer items-center gap-6 rounded-4 px-6 py-4 transition-colors hover:bg-white/10 hover:text-white",
                    terminalOpen ? "bg-white/10 text-white/80" : "text-white/40",
                  )}
                >
                  <TerminalIcon aria-hidden="true" className="shrink-0 size-14" />
                  <kbd className="hidden rounded-4 border border-white/15 px-5 py-1 font-mono text-[11px] text-white/55 leading-none sm:inline-block">
                    {mod} J
                  </kbd>
                </button>
                <button
                  type="button"
                  aria-label={labels.search}
                  onClick={() => setSearchOpen(true)}
                  className="flex cursor-pointer items-center gap-6 rounded-4 px-6 py-4 text-white/40 transition-colors hover:bg-white/10 hover:text-white"
                >
                  <SearchIcon aria-hidden="true" className="shrink-0 size-14" />
                  <kbd className="hidden rounded-4 border border-white/15 px-5 py-1 font-mono text-[11px] text-white/55 leading-none sm:inline-block">
                    {mod} K
                  </kbd>
                </button>
              </div>
            </div>

            {/* BODY */}
            <div ref={bodyRef} className="relative flex min-h-0 flex-1">
              <aside className="flex shrink-0 flex-col" style={{ width: explorerW, maxWidth: "60%" }}>
                <RepoFileTree
                  tree={tree}
                  openPaths={openPaths}
                  activePath={activePath}
                  onToggleFolder={toggleFolder}
                  onOpenFile={openFile}
                />
              </aside>
              <button
                type="button"
                aria-label={labels.resizeExplorer}
                onKeyDown={onExplorerKeyDown}
                {...resizeHandlers("x")}
                className="group relative w-3 shrink-0 cursor-col-resize touch-none outline-none"
              >
                <span className="pointer-events-none absolute inset-y-0 left-1/2 w-px -translate-x-1/2 transition-colors bg-white/10 group-hover:bg-white/30" />
              </button>
              <div className="flex min-w-0 flex-1 flex-col">
                <div className="flex min-h-0 flex-1 flex-col">
                  <RepoEditor path={activePath} value={editorValue} onChange={onEditorChange} />
                </div>
                {terminalOpen ? (
                  <>
                    <button
                      type="button"
                      aria-label={labels.resizeTerminal}
                      onKeyDown={onTerminalKeyDown}
                      {...resizeHandlers("y")}
                      className="group relative h-3 shrink-0 cursor-row-resize touch-none outline-none"
                    >
                      <span className="pointer-events-none absolute inset-x-0 top-1/2 h-px -translate-y-1/2 transition-colors bg-white/10 group-hover:bg-white/30" />
                    </button>
                    <div className="flex min-h-0 shrink-0 flex-col" style={{ height: terminalH, maxHeight: "70%" }}>
                      <RepoTerminal
                        key={edition.id}
                        edition={edition}
                        tree={tree}
                        cta={edition.cta}
                        placeholder={content.terminalHint}
                        title={content.terminalTitle}
                        request={request}
                        onOpenFile={openFile}
                        onAddFile={onAddFile}
                      />
                    </div>
                  </>
                ) : null}
              </div>
              {terminalOpen ? (
                <button
                  type="button"
                  aria-label={labels.resizeBoth}
                  tabIndex={-1}
                  {...resizeHandlers("xy")}
                  className="absolute z-2 size-5 -translate-x-1/2 translate-y-1/2 cursor-nesw-resize touch-none outline-none"
                  style={{ left: explorerW, bottom: terminalH }}
                />
              ) : null}
            </div>

            {/* FOOTER */}
            <div className="flex h-28 shrink-0 items-center justify-between gap-12 border-white/10 border-t px-16 font-mono text-caption-10 text-white/40 uppercase tracking-wide">
              <div className="flex min-w-0 items-center gap-10">
                <span className="flex shrink-0 items-center gap-5">
                  <span aria-hidden="true" className="text-white/30">
                    ⎇
                  </span>
                  {repo.branch}
                </span>
                <span className="hidden h-10 w-px shrink-0 bg-white/10 sm:block" />
                <span className="flex min-w-0 items-center gap-6">
                  {repo.isRecent ? (
                    <span
                      aria-hidden="true"
                      className="size-6 shrink-0 rounded-full animate-pulse bg-[#d6a878] motion-reduce:animate-none"
                    />
                  ) : null}
                  <span className="truncate">{repo.updatedLabel}</span>
                </span>
              </div>
              <button
                type="button"
                title={labels.commitGraphTitle}
                aria-label={labels.commitGraphLabel}
                onClick={showCommitGraph}
                className="flex shrink-0 cursor-pointer items-center gap-6 rounded-4 px-6 py-3 uppercase leading-none tracking-wide transition-colors hover:bg-white/10 hover:text-white"
              >
                <CommitsIcon aria-hidden="true" className="size-[1.05em] shrink-0 text-white/30" />
                <span className="leading-none">
                  {repo.totalCommits} {labels.commits}
                </span>
              </button>
            </div>

            {searchOpen ? (
              <RepoSearch
                tree={tree}
                rootName={tree.name}
                placeholder={labels.searchPlaceholder}
                label={labels.searchInput}
                onSelect={onSearchSelect}
                onClose={closeSearch}
              />
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

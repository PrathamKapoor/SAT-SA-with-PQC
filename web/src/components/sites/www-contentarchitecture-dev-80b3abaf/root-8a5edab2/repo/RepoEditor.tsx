"use client";

import {
  useCallback,
  useLayoutEffect,
  useMemo,
  useRef,
  type KeyboardEvent,
  type PointerEvent,
} from "react";

import { useElementSize } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/hooks";

import { highlight } from "./highlight";
import { baseName, highlightMode } from "./model";

export interface RepoEditorProps {
  /** Repo-relative path of the open file ("README.md"). */
  path: string;
  /** File contents (controlled). */
  value: string;
  /** Edits are kept by the parent per path. */
  onChange: (value: string) => void;
}

/** Minimap: at most 4px per row, bars 0.5px per character capped at 52px (measured on the live site). */
const MINIMAP_MAX_ROW = 4;
const MINIMAP_MAX_BAR = 52;
const MINIMAP_CHAR_WIDTH = 0.5;
const MINIMAP_INSET = 16;
const TAB = "  ";

/**
 * Editable file pane: a transparent textarea over a syntax-highlighted `<pre>`, with a line-number
 * gutter and a click/drag minimap, all kept in scroll sync.
 */
export function RepoEditor({ path, value, onChange }: RepoEditorProps) {
  const name = baseName(path);
  const mode = highlightMode(name);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const overlayRef = useRef<HTMLPreElement>(null);
  const gutterRef = useRef<HTMLDivElement>(null);
  const minimapRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);

  const minimapSize = useElementSize(minimapRef);
  const textareaSize = useElementSize(textareaRef);

  const lines = useMemo(() => value.split("\n"), [value]);
  const lineCount = lines.length;
  const lineNumbers = useMemo(
    () => Array.from({ length: lineCount }, (_, i) => i + 1).join("\n"),
    [lineCount],
  );
  const highlighted = useMemo(() => highlight(value, mode), [value, mode]);

  const avail = minimapSize.height - MINIMAP_INSET;
  const rowH = Math.max(0, Math.min(MINIMAP_MAX_ROW, avail / lineCount));
  const minimapH = lineCount * rowH;

  const minimapRows = useMemo(
    () =>
      lines.map((line, i) => {
        const trimmed = line.trimStart();
        const indent = line.length - trimmed.length;
        return (
          <div key={i} className="flex items-center" style={{ height: rowH }}>
            <div
              className="rounded-full bg-white/20"
              style={{
                marginLeft: Math.min(MINIMAP_MAX_BAR, indent * MINIMAP_CHAR_WIDTH),
                width: Math.min(MINIMAP_MAX_BAR, trimmed.length * MINIMAP_CHAR_WIDTH),
                height: Math.max(0, rowH - 1),
              }}
            />
          </div>
        );
      }),
    [lines, rowH],
  );

  /** Mirror the textarea's scroll onto the overlay, the gutter and the minimap viewport box. */
  const sync = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    const { scrollTop, scrollLeft, scrollHeight, clientHeight } = textarea;
    const overlay = overlayRef.current;
    if (overlay) {
      overlay.scrollTop = scrollTop;
      overlay.scrollLeft = scrollLeft;
    }
    const gutter = gutterRef.current;
    if (gutter) gutter.scrollTop = scrollTop;
    const viewport = viewportRef.current;
    if (viewport) {
      const vpH = scrollHeight > 0 ? (clientHeight / scrollHeight) * minimapH : minimapH;
      const vpY = scrollHeight > 0 ? (scrollTop / scrollHeight) * minimapH : 0;
      viewport.style.transform = `translateY(${vpY}px)`;
      viewport.style.height = `${vpH}px`;
    }
  }, [minimapH]);

  // A newly opened file starts at the top.
  useLayoutEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.scrollTop = 0;
    textarea.scrollLeft = 0;
  }, [path]);

  // Re-sync after content, file, minimap or textarea size changes.
  useLayoutEffect(() => {
    sync();
  }, [sync, value, path, textareaSize.width, textareaSize.height]);

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Tab" || event.shiftKey || event.altKey || event.ctrlKey || event.metaKey) return;
    event.preventDefault();
    const textarea = event.currentTarget;
    textarea.setRangeText(TAB, textarea.selectionStart, textarea.selectionEnd, "end");
    onChange(textarea.value);
  };

  const scrollFromMinimap = (event: PointerEvent<HTMLButtonElement>) => {
    const textarea = textareaRef.current;
    if (!textarea || minimapH <= 0) return;
    const y = event.clientY - event.currentTarget.getBoundingClientRect().top;
    textarea.scrollTop = (y / minimapH) * textarea.scrollHeight - textarea.clientHeight / 2;
  };

  const handleMinimapPointerDown = (event: PointerEvent<HTMLButtonElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    scrollFromMinimap(event);
  };

  const handleMinimapPointerMove = (event: PointerEvent<HTMLButtonElement>) => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) scrollFromMinimap(event);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="shrink-0 border-white/10 border-b px-16 py-10 font-mono text-caption-10 text-white/40 uppercase tracking-wide">
        {name}
      </div>
      <div className="flex min-h-0 flex-1 bg-black-deep/30">
        <div ref={gutterRef} className="shrink-0 select-none overflow-hidden border-white/10 border-r">
          <pre
            aria-hidden="true"
            className="whitespace-pre pt-16 pr-8 pb-16 pl-12 text-right font-mono text-caption-10 text-white/25 leading-relaxed"
          >
            {lineNumbers}
          </pre>
        </div>
        <div className="relative flex min-h-0 min-w-0 flex-1">
          <pre
            ref={overlayRef}
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 z-0 overflow-hidden whitespace-pre pt-16 pr-16 pb-16 pl-12 font-mono text-caption-10 text-ghost-grey leading-relaxed"
          >
            {highlighted}
          </pre>
          <textarea
            ref={textareaRef}
            aria-label={`${name} contents`}
            spellCheck={false}
            autoCapitalize="off"
            autoCorrect="off"
            wrap="off"
            value={value}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={handleKeyDown}
            onScroll={sync}
            className="scrollbar-thin relative z-2 min-h-0 min-w-0 flex-1 resize-none whitespace-pre bg-transparent pt-16 pr-16 pb-16 pl-12 font-mono text-caption-10 text-transparent leading-relaxed caret-white/80 outline-none"
            data-lenis-prevent=""
          />
        </div>
        <div
          ref={minimapRef}
          className="relative hidden w-64 shrink-0 overflow-hidden border-white/10 border-l sm:block"
        >
          <button
            type="button"
            aria-label="Scroll via minimap"
            className="relative block w-full cursor-pointer touch-none px-6 text-left outline-none"
            style={{ height: minimapH }}
            onPointerDown={handleMinimapPointerDown}
            onPointerMove={handleMinimapPointerMove}
          >
            {minimapRows}
            <div
              ref={viewportRef}
              aria-hidden="true"
              className="pointer-events-none absolute inset-x-0 top-0 bg-white/10 ring-1 ring-white/15 ring-inset"
            />
          </button>
        </div>
      </div>
    </div>
  );
}

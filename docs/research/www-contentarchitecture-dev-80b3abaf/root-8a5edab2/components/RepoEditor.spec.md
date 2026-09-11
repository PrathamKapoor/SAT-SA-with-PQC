# RepoEditor Specification (B7b)

## Overview
- **Target files:**
  - `…/root-8a5edab2/repo/RepoEditor.tsx`: replace the foreman stub and keep its props interface **exactly**
  - `…/root-8a5edab2/repo/highlight.tsx`: a new pure tokenizer that returns React nodes
- **Screenshot:** `docs/design-references/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/05-repo-1440.jpeg` (the centre pane showing README.md).
- **Interaction model:** an editable textarea with a syntax-highlighted overlay, line-number gutter and code minimap, all scroll-synced. The minimap is click/drag-to-scroll.

## Props contract (in the stub; do not change)
```ts
export interface RepoEditorProps {
  path: string;                       // repo-relative path of the open file ("README.md")
  value: string;                      // file contents (controlled)
  onChange: (value: string) => void;  // edits are kept by the parent per path
}
export function RepoEditor(props: RepoEditorProps): JSX.Element
```
Use `baseName`, `highlightMode` from `./model`.

## DOM (exact live classes)
```
<div class="flex min-h-0 flex-1 flex-col">
  <div class="shrink-0 border-white/10 border-b px-16 py-10 font-mono text-caption-10 text-white/40 uppercase tracking-wide">{baseName(path)}</div>
  <div class="flex min-h-0 flex-1 bg-black-deep/30">
    <!-- gutter -->
    <div class="shrink-0 select-none overflow-hidden border-white/10 border-r">
      <pre aria-hidden="true" class="whitespace-pre pr-8 pl-12 text-right font-mono text-caption-10 text-white/25 leading-relaxed" style="padding-top:16px;padding-bottom:16px">1\n2\n…N</pre>
    </div>
    <!-- code -->
    <div class="relative flex min-h-0 min-w-0 flex-1">
      <pre aria-hidden="true" class="pointer-events-none absolute inset-0 z-0 overflow-hidden whitespace-pre pr-16 pl-12 font-mono text-caption-10 text-ghost-grey leading-relaxed" style="padding-top:16px;padding-bottom:16px">{highlight(value, mode)}</pre>
      <textarea aria-label="{baseName} contents" spellcheck="false" autocapitalize="off" autocorrect="off" wrap="off"
        class="scrollbar-thin relative z-2 min-h-0 min-w-0 flex-1 resize-none whitespace-pre bg-transparent pr-16 pl-12 font-mono text-caption-10 text-transparent leading-relaxed caret-white/80 outline-none"
        style="padding-top:16px;padding-bottom:16px" data-lenis-prevent />
    </div>
    <!-- minimap (hidden below sm) -->
    <div class="relative hidden w-64 shrink-0 overflow-hidden border-white/10 border-l sm:block">
      <button type="button" aria-label="Scroll via minimap" class="relative block w-full cursor-pointer touch-none px-6 text-left outline-none" style="height:{H}px">
        …one row per line: <div class="flex items-center" style="height:{rowH}px"><div class="rounded-full bg-white/20" style="margin-left:{indent}px;width:{w}px;height:{rowH-1}px"/></div>
        <div aria-hidden="true" class="pointer-events-none absolute inset-x-0 top-0 bg-white/10 ring-1 ring-white/15 ring-inset" style="transform:translateY({vpY}px);height:{vpH}px"/>
      </button>
    </div>
  </div>
</div>
```
- The textarea text is transparent; the highlighted `<pre>` underneath shows the colours. Both **must** share font, size, line-height (`leading-relaxed` = 1.625, ≈22.33px at 1440), padding and `whitespace-pre`, so the caret lines up exactly.
- **Gutter:** line count = `value.split("\n").length`.

## Scroll sync
- On textarea `scroll`, set `overlayPre.scrollTop/scrollLeft = textarea.scrollTop/scrollLeft` and `gutterContainer.scrollTop = textarea.scrollTop`. Also run the sync after `value` or `path` changes, and reset scroll to 0 when `path` changes.
- The minimap viewport box updates from the same handler.

## Minimap maths (measured on the live site)
- `avail = minimapContainer.clientHeight − 16` (use a ResizeObserver).
- `rowH = min(4, avail / lines)`, and button height `H = lines × rowH`.
- Each bar:
  - `width = min(52, visibleChars × 0.5)` px, where visibleChars = the line length after trimming leading whitespace
  - `margin-left = min(52, leadingSpaces × 0.5)` px
  - `height = rowH − 1`
  - an empty line → width 0
- Viewport box: `vpH = clientHeight / scrollHeight × H` (= H when not scrollable), and `vpY = scrollTop / scrollHeight × H`.
- **Pointer (pointerdown plus drag with pointer capture) on the button:** `textarea.scrollTop = (y / H) × scrollHeight − clientHeight / 2`, where y = the pointer offset in the button.
- Measured examples:
  - README (155 lines, avail 405): rowH 2.6129, bars 18px for "# The Content Architecture (Next.js)"
  - AGENTS.md (4 lines): rowH 4, H 16

## Highlighting rules (`highlight.tsx`: `export function highlight(text: string, mode: HighlightMode): ReactNode[]`)
Colours are Tailwind classes on `<span>`s; unstyled runs are plain `<span>`s (text colour inherits `text-ghost-grey`). Output must reproduce the text **exactly**, including the trailing newline.
- **markdown**:
  - A line starting with `#` (ATX heading) → the whole line in `text-[#9fb6d6]`.
  - A fenced block, from a line starting with <code>```</code> through the closing fence inclusive → a single span `text-white/40`, with no inline parsing inside.
  - A list marker at line start (`-`, `*`, or `\d+.`, after optional indentation) → the marker alone in `text-white/35`; the rest of the line is parsed inline.
  - **Inline** (outside fences and headings):
    - `` `code` `` → `text-[#d6a878]`
    - `**bold**` → `text-white/90`
    - `[label](url)` (the whole construct) → `text-white/75`
- **slash-comments** (ts/tsx/js/mjs/json/jsonc/css/hbs): a line whose trimmed start is `//`, `/*`, `*` or `*/` → `text-white/30 italic`. Everything else is plain.
- **hash-comments** (yml/yaml/toml/sh/.gitignore/.npmrc/.nvmrc): a line starting (after whitespace) with `#` → `text-white/30 italic`.
- **plain**: a single plain span.
- Memoise with `useMemo([value, mode])`. The README (≈9.6k chars) must re-highlight per keystroke without jank.

## Behaviours
- **Typing:** `onChange(e.target.value)`. Tab inserts two spaces (preventDefault, then set the value and caret via `setRangeText`).
- **Hover:** none except the cursor. The minimap button is `cursor-pointer`.
- The textarea gets the global accent focus ring from base CSS; do not add any other outline.

## Responsive
- **Below sm (640px):** the minimap is hidden. Everything else is identical.
- **Desktop:** the pane fills the space between the explorer and the minimap. At 1440 the textarea is ≈411px tall with the 200px terminal open.

## Verify
`npx tsc --noEmit` and `npx eslint` on both files must pass. Add a tiny self-check: `highlight("# A\n- `b` **c** [d](e)\n", "markdown")` must round-trip the text (concatenate the node texts in a quick node script or a unit assertion in a comment).

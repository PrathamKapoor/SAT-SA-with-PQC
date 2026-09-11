# RepoSection Specification (B7d: wrapper, search palette, content)

## Overview
- **Target files** (all yours):
  - `…/root-8a5edab2/RepoSection.tsx`: exports `RepoContent` and `RepoSection({ content })`
  - `…/root-8a5edab2/repo/RepoSearch.tsx`: the Ctrl K palette
  - `…/root-8a5edab2/content/repo.ts`: exports `repoContent`
- **Import, do not edit:** `./repo/model` (types and helpers), `./repo/RepoFileTree`, `./repo/RepoEditor` and `./repo/RepoTerminal`. The last three are stubs with their **final props**; other builders are filling them in, so code against the props.
- **Screenshots:** `05-repo-1440.jpeg` and `22-mobile-repo-390.jpeg`.
- **Interaction model:** click, keyboard and drag.

## Content contract
```ts
export interface RepoEditionContent extends RepoEdition { cta: RepoCta }   // from ./repo/model
export interface RepoContent {
  id: string;                 // "the-repo"
  title: string;              // "This is the actual repo."
  terminalTitle: string;      // "Terminal"
  terminalHint: string;       // "try: git, ls, tree, plop, cat README.md"
  editions: RepoEditionContent[];
  labels: { hideTerminal: string; showTerminal: string; search: string; searchPlaceholder: string;
            resizeExplorer: string; resizeTerminal: string; resizeBoth: string;
            commitGraphTitle: string; commitGraphLabel: string; commits: string };
}
```
- **content/repo.ts:** `import ide from "../data/ide.json"`. Its shape is `{ title, terminalHint, cta: { label, link: { href }, prices: { next: { price, listPrice }, astro: {…} } }, editions: [{ id, label, ariaLabel, repo, tree }] }`.
  - Map each edition, casting its tree via `as unknown as RepoFolderNode`.
  - Set `cta: { label: "get-access", note: "€399 · was €549 · one-time", href: "#pricing" }`, building the note from `prices[id]`.
  - **Labels:** "Hide terminal", "Show terminal", "Search files", "Search project files...", "Resize file explorer", "Resize terminal", "Resize file explorer and terminal", "Show the commit graph", "Show the commit graph in the terminal", "commits".

## DOM (exact live classes; the section is off-white and the IDE is a dither frame)
```
<div id={content.id} data-page-builder-section="ideSection" class="h-svh bg-off-white px-16 py-72 text-black lg:p-80">
 <div class="h-full w-full">
  <div class="rounded-8 p-6 shadow-lg ring ring-black-deep transition-colors duration-300 lg:p-8 bg-black-deep bg-dither h-full">
   <div class="relative isolate flex h-full flex-col overflow-hidden rounded-4 bg-black text-white ring-1 ring-white/10">
    HEADER · BODY · FOOTER · (search palette overlay when open)
```
- **HEADER** `div.relative flex h-34 shrink-0 items-center justify-center border-white/10 border-b px-16`:
  - **Left** `div.absolute top-1/2 left-8 -translate-y-1/2` → `div.relative isolate flex items-center gap-2 rounded-4 bg-white/5 p-2`, with one button per edition:
    - `button type=button aria-label={ed.ariaLabel} aria-pressed` classes `relative cursor-pointer rounded-4 px-6 py-2 font-mono text-caption-10 uppercase tracking-wide transition-colors`, plus `text-white` when active or `text-white/40 hover:text-white` when not
    - label in `span.relative`
    - **The active pill** is ONE `span aria-hidden class="absolute inset-y-2 left-0 rounded-4 bg-white/10 transition-[transform,width] duration-300 ease-[cubic-bezier(0.23,1,0.32,1)] motion-reduce:transition-none"` inside the group. Translate it to the active button's `offsetLeft` and width (measure in a layout effect and on resize), so it slides.
  - **Centre** `span.max-w-1/3 truncate font-mono text-caption-10 text-white/40 uppercase tracking-wide` → {title}
  - **Right** `div.absolute top-1/2 right-8 flex -translate-y-1/2 items-center gap-4`:
    - The terminal toggle button (`aria-label` = hide/show label, `aria-pressed={terminalOpen}`) with classes `flex cursor-pointer items-center gap-6 rounded-4 px-6 py-4 transition-colors hover:bg-white/10 hover:text-white`, plus `bg-white/10 text-white/80` when open or `text-white/40` when closed → `<TerminalIcon className="shrink-0 size-14"/>`, then `<kbd class="hidden rounded-4 border border-white/15 px-5 py-1 font-mono text-[11px] text-white/55 leading-none sm:inline-block">{mod} J</kbd>`
    - The search button (`aria-label` = search) with classes `flex cursor-pointer items-center gap-6 rounded-4 px-6 py-4 text-white/40 transition-colors hover:bg-white/10 hover:text-white` → `<SearchIcon className="shrink-0 size-14"/>` plus a kbd `{mod} K`
    - `mod` = "⌘" on Mac (`/Mac|iPhone|iPad/.test(navigator.platform)`, after mount) and "Ctrl" otherwise.
- **BODY** `div.relative flex min-h-0 flex-1`:
  - `aside.flex shrink-0 flex-col` with inline `style={{ width: explorerW, maxWidth: "60%" }}` → `<RepoFileTree …/>`
  - `button aria-label={resizeExplorer} class="group relative w-3 shrink-0 cursor-col-resize touch-none outline-none"` → `span.pointer-events-none absolute inset-y-0 left-1/2 w-px -translate-x-1/2 transition-colors bg-white/10 group-hover:bg-white/30`
  - `div.flex min-w-0 flex-1 flex-col`:
    - `div.flex min-h-0 flex-1 flex-col` → `<RepoEditor …/>`
    - if the terminal is open:
      - `button aria-label={resizeTerminal} class="group relative h-3 shrink-0 cursor-row-resize touch-none outline-none"` → `span.pointer-events-none absolute inset-x-0 top-1/2 h-px -translate-y-1/2 transition-colors bg-white/10 group-hover:bg-white/30`
      - `div.flex min-h-0 shrink-0 flex-col` with `style={{ height: terminalH, maxHeight: "70%" }}` → `<RepoTerminal key={edition.id} …/>`
  - if the terminal is open, the corner handle: `button aria-label={resizeBoth} tabIndex={-1} class="absolute z-2 size-5 -translate-x-1/2 translate-y-1/2 cursor-nesw-resize touch-none outline-none"` with `style={{ left: explorerW, bottom: terminalH }}`
- **FOOTER** `div.flex h-28 shrink-0 items-center justify-between gap-12 border-white/10 border-t px-16 font-mono text-caption-10 text-white/40 uppercase tracking-wide`:
  - `div.flex min-w-0 items-center gap-10`, containing:
    - `span.flex shrink-0 items-center gap-5` → `<span aria-hidden class="text-white/30">⎇</span>{repo.branch}`
    - `span.hidden h-10 w-px shrink-0 bg-white/10 sm:block`
    - `span.flex min-w-0 items-center gap-6` → (if `isRecent`) `span[aria-hidden].size-6 shrink-0 rounded-full animate-pulse bg-[#d6a878] motion-reduce:animate-none`, then `span.truncate {updatedLabel}`
  - `button title={commitGraphTitle} aria-label={commitGraphLabel} class="flex shrink-0 cursor-pointer items-center gap-6 rounded-4 px-6 py-3 uppercase leading-none tracking-wide transition-colors hover:bg-white/10 hover:text-white"` → `<CommitsIcon className="size-[1.05em] shrink-0 text-white/30"/>` + `span.leading-none "{totalCommits} {commits}"`

## State (all in RepoSection)
- `editionIndex` (0).
- `tree` (the current edition tree; plop appends via `addFile`).
- `openPaths` (`defaultOpenPaths(tree)`), `activePath` (`defaultActivePath`), and `edits: Record<path, string>`.
- `terminalOpen` (true), `explorerW` (240), `terminalH` (200), `searchOpen`, and `request` ({id, command} | undefined).
- **Edition switch:** reset tree, openPaths, activePath, edits and request to that edition's defaults. The terminal remounts via its key.
- **openFile(path):** set `activePath` and add every ancestor folder to `openPaths`.
- **Editor wiring:** `value = edits[activePath] ?? (getNode(tree, activePath) as file).content`. `onChange` stores the value in `edits`.
- **Commits button:** `terminalOpen = true` and `request = { id: prev + 1, command: "git" }`.
- **Shortcuts** (a window keydown handler, active only while the section is ≥ 30% in view, via `useInView` from shared hooks with `threshold: 0.3`; each call preventDefault):
  - Ctrl/⌘ + J toggles the terminal
  - Ctrl/⌘ + K opens the search palette
- **Resizers:** pointerdown → setPointerCapture → pointermove updates the size (relative to the body container rect); release ends the drag.
  - Clamp explorer 140px … 60% of the body width.
  - Clamp the terminal 72px … 70% of the column height.
  - The corner changes both.
  - Keyboard on the two focusable resizers: arrows ±16px.
  - During a drag, set `document.body.style.cursor` and `userSelect = none`.

## RepoSearch (`repo/RepoSearch.tsx`)
- **Props:** `{ tree: RepoFolderNode; rootName: string; placeholder: string; label: string; onSelect(path): void; onClose(): void }`. Render it inside the IDE window when `searchOpen`.
- **DOM:**
  - `div.absolute inset-0 z-3 flex items-start justify-center` containing:
    - a backdrop `div.absolute inset-0 bg-black-deep/50` (fades in 150ms; a click closes)
    - the panel `div.relative mt-10 flex max-h-[min(70%,440px)] w-[min(92%,560px)] flex-col overflow-hidden rounded-8 bg-black shadow-2xl ring-1 ring-white/15`, entering from opacity 0 / translateY(-4px) scale(.98) over 150ms ease-out
  - Inside the panel:
    - `input aria-label={label} placeholder class="shrink-0 border-white/10 border-b bg-transparent px-16 py-12 font-mono text-caption-10 text-white caret-accent outline-none placeholder:text-white/30"` (autofocus)
    - a list `div.scrollbar-thin min-h-0 flex-1 overflow-y-auto py-6` with `data-lenis-prevent`
  - **Result row:** `button type=button class="flex w-full cursor-pointer items-center gap-10 px-16 py-6 text-left font-mono text-caption-10"`, plus `bg-white/10` when selected or `hover:bg-white/[0.04]` otherwise. It contains:
    - the file icon (the same map as the tree; see `fileIconKind`) with `className="size-[1.05em] shrink-0 text-white/50"`
    - `span.shrink-0 text-white/90 {name}`
    - `span.truncate text-white/35 "{rootName}/{parentPath}/"` (just `"{rootName}/"` at the root)
- **Results** from `walkFiles(tree)`:
  - An empty query lists every file in tree order.
  - Otherwise, case-insensitive ranking: name startsWith, then name includes, then path includes. Ties keep tree order. Cap at 60 results.
- **Keys:**
  - ArrowUp/Down move the selection (clamped, scrolled into view with `block: "nearest"`)
  - Enter selects
  - Escape closes
- **Select:** `onSelect(path)` → the parent calls `openFile` and closes the palette.

## Responsive
Same structure at every width. The kbd hints and the footer divider hide below `sm`; the editor minimap hides below `sm` (in RepoEditor). The section is always `h-svh`, with the padding changing from `px-16 py-72` to `lg:p-80`.

## Verify
`npx tsc --noEmit` and `npx eslint` on your files must pass. Do not modify the stubs, `model.ts`, or shared files.

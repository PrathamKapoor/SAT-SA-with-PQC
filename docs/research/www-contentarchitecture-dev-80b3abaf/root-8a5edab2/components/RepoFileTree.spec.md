# RepoFileTree Specification (B7a)

## Overview
- **Target file:** `src/components/sites/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/repo/RepoFileTree.tsx` (replace the foreman stub, and keep its exported props interface **exactly**).
- **Screenshot:** `docs/design-references/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/05-repo-1440.jpeg` (the left column of the IDE).
- **Interaction model:** click-driven. Folders toggle and files open. The parent (`RepoSection`) owns all state; this component is controlled.

## Props contract (already in the stub; do not change)
```ts
import type { RepoFolderNode } from "./model";
export interface RepoFileTreeProps {
  tree: RepoFolderNode;              // edition root; render its children (the root row itself is NOT shown)
  openPaths: ReadonlySet<string>;    // repo-relative folder paths that are expanded
  activePath: string;                // repo-relative path of the file in the editor
  onToggleFolder: (path: string) => void;
  onOpenFile: (path: string) => void;
}
export function RepoFileTree(props: RepoFileTreeProps): JSX.Element
```
Use `joinPath` and `fileIconKind` from `./model`. Paths exclude the root name: `app`, `app/(web)`, `README.md`.

## DOM (exact classes from the live site)
```
<nav aria-label="File explorer" class="flex min-h-0 flex-1 flex-col justify-between gap-16">
  <div class="scrollbar-thin min-h-0 flex-1 overflow-auto py-12" data-lenis-prevent>
    <ul class="w-max min-w-full">  … one <li> per child of the root …
```
- **Folder `li`**:
  - `<button type="button" aria-expanded={open} style={{ paddingLeft: 10 + depth * 14 }}>`
    - classes: `flex w-full items-center gap-6 py-3 pr-10 text-left font-mono text-caption-10 uppercase tracking-wide outline-none transition-colors duration-100 cursor-pointer text-white/60 hover:bg-white/[0.04] hover:text-white/90`
    - children, in order:
      1. `<ChevronRightIcon className={cn("size-[0.85em] shrink-0 opacity-50 transition-transform duration-200 ease-out motion-reduce:transition-none", open && "rotate-90")} />`
      2. `open ? <FolderOpenIcon className="size-[1.05em] shrink-0" /> : <FolderIcon className="size-[1.05em] shrink-0" />`
      3. `<span className="whitespace-nowrap">{name}</span>`
  - Then the collapsible children wrapper (a CSS grid-rows animation):
    `<div className="grid transition-[grid-template-rows] duration-200 ease-out motion-reduce:transition-none" style={{ gridTemplateRows: open ? "1fr" : "0fr" }}><div className="overflow-hidden"><ul>…children…</ul></div></div>`
  - Collapsed folders set `inert` on the inner wrapper so hidden rows are not tabbable. For performance you may render a collapsed folder's children lazily: only after it has been opened once, then keep them mounted so the close animation plays.
- **File `li`**:
  - `<button type="button" style={{ paddingLeft: 10 + depth * 14 }} aria-current={active ? "true" : undefined}>`
    - classes: the same base as the folder, but with `text-white/55 hover:bg-white/[0.04] hover:text-white/90` when inactive and `bg-white/[0.06] text-white` when active (no hover classes when active)
    - children:
      1. a spacer `<span className="size-[0.85em] shrink-0" aria-hidden="true" />`, which aligns with the folder chevrons
      2. the file icon with `className="size-[1.05em] shrink-0 text-current/70"`
      3. `<span className="whitespace-nowrap">{name}</span>`
- `depth` = 0 for root children, then +1 per level (so 10px, 24px, 38px, 52px …).
- **Icon map** (`fileIconKind(name)` → import from `@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/icons`):
  - `component` → `ComponentFileIcon`
  - `code` → `CodeFileIcon`
  - `json` → `JsonFileIcon`
  - `css` → `CssFileIcon`
  - `image` → `ImageFileIcon`
  - `config` → `ConfigFileIcon`
  - `text` → `TextFileIcon`
  - `file` → `FileIcon`

## Behaviours
- A folder click calls `onToggleFolder(path)`; a file click calls `onOpenFile(path)`.
- When `activePath` changes (for example from the search palette, `open` in the terminal, or plop), scroll the active row into view inside the scroll container only if it is off-screen: `el.scrollIntoView({ block: "nearest" })`. The parent opens the ancestor folders.
- **Keyboard:** the buttons are natively focusable, and the global focus ring comes from the base CSS. Optionally, ArrowUp/ArrowDown move focus between visible rows, and ArrowRight/ArrowLeft open/close a focused folder.
- **Hover:** background `white/[0.04]` and text → `white/90`, over a 100ms colour transition.

## Data facts (CA)
- The Next.js tree has 468 nodes. It opens with `app` and `features` expanded; `README.md` is active.
- The Astro tree has 493 nodes. It opens with `src`, `src/features` and `src/pages` expanded.
- Order is exactly the data order (folders first, then files; the data is already sorted).
- Names like `(web)`, `[[...uri]]`, `@modal`, `(.)authors` are literal. Render them as text.

## Responsive
Identical at every width. The parent `aside` sets the width (240px default, `max-width: 60%`). The row list is `w-max min-w-full`, so long names scroll horizontally inside the explorer.

## Verify
`npx tsc --noEmit` and `npx eslint src/components/sites/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/repo/RepoFileTree.tsx` must pass.

# Builder brief (applies to every component builder)

You are building one piece of a Next.js 16 + React 19 + TypeScript (strict) + Tailwind v4 clone of https://www.contentarchitecture.dev, inside a git **worktree** of `C:\Projects\ai-website-cloner-template`.

## 0. Worktree setup (do first)
- Your cwd is the worktree root. It has no `node_modules`, so link the main checkout's copy (Windows junction, no admin needed):
  `cmd //c mklink /J node_modules C:\\Projects\\ai-website-cloner-template\\node_modules` (from Git Bash), or in PowerShell: `New-Item -ItemType Junction -Path node_modules -Target C:\Projects\ai-website-cloner-template\node_modules`.
- Never commit `node_modules` (it is gitignored). Never run `npm install`.

## 1. Design system (already in `src/app/globals.css`, do not edit it)
- **Spacing unit is 1px:** `p-16` = 16px, `h-48` = 48px, `pt-160` = 160px, `size-6` = 6px. Radii are `rounded-2/4/8/full`.
- **Colours:** `black` = #232323 (NOT pure black), `black-deep` = #000, `white`, `off-white` #f1eee7, `dark-grey` #5b5a56, `ghost-grey` #dedede, `mid-grey` #cbcbcb, `accent` #ff9100.
- **Type** (fluid; each sets size and line-height): `text-ui`, `text-caption-10`, `text-caption-20`, `text-body-10`, `text-body-20`, `text-body-30` (body default), `text-headline-10`, `text-headline-20`. Fonts are `font-sans` (Geist) and `font-mono` (Geist Mono).
- **Animations:** `animate-fade-in`, `animate-cursor-blink`, `animate-status-ping`, `animate-hero-scroll-cue`, `animate-minimap-scan`, `animate-minimap-scan-counter`, `animate-marquee-left`.
- **Utilities:** `scrollbar-thin` and `bg-dither` (4px checker used by the frames). The only layout breakpoint is `lg:` (1024px).
- The DOM reference files contain the **live site's exact class strings**. Copy them verbatim: they compile to identical CSS here because the theme is identical. Drop `style="opacity:1; transform:none"` leftovers (animation end states).

## 2. Shared primitives (import from `@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/…`; do not edit them, report bugs instead)
- `Odometer` — `<Odometer text="Features" />` renders the sr-only text plus the slot-machine glyph columns. The **ancestor** must carry `[--odometer-progress:0] motion-safe:hover:[--odometer-progress:1]`. In the DOM files, `<Odometer text="…"/>` marks where to use it.
- `EmailCapture` — `<EmailCapture copy={{label, placeholder, ctaText, ctaRightText?, successMessage, errorMessage}} buttonVariant="light" onSuccess? />` (CA newsletter form with validation + status line).
- `CaButton` — (includes the live hover colours: light → white, dark → black-deep) `<CaButton leftText="Get" rightText="access" variant="dark|light" showPulseDot href="/#pricing" />` is the split pill with connector. It also accepts `type`, `onClick`, `className`, `external` and `disabled`.
- `Connector` — `<Connector orientation="vertical|horizontal" length={26} className="text-black" />` is the 6px concave bridge.
- `PulseDot` — `<PulseDot className="absolute top-8 right-8" size="size-6" />`.
- `DitherFrame` — `<DitherFrame title="Common problems" titleRight={…} draggable innerClassName="…">body</DitherFrame>`: the frame, inner black window and 26px title bar. Its markup matches the DOM files' `rounded-8 p-6 … bg-black-deep` frame.
- `Marquee` — `<Marquee duration={14.76}>{item}</Marquee>`, an infinite left marquee.
- `Reveal` — `<Reveal as="h2" className="…">text</Reveal>` fades in on viewport enter (use it for every `data-split="lines"` block). `<Reveal rise delay={300}>` fades in and rises from 48px (use for CTAs).
- `AsciiImage` — `<AsciiImage cells levels cols rows aspect label className />` for precomputed ASCII art; the type is `AsciiGrid`.
- `DeferredMount` — `<DeferredMount placeholder={…} releaseMargin="100%" className>` for heavy children.
- `GlyphField` and `SpiralScene` are WebGL scenes (other builders own them). Import and use them by their props; they currently render a solid-colour stub.
- `CursorLabel` and `setupCursorTracking`; icons in `icons.tsx` (`LogoMark`, `TerminalIcon`, `SearchIcon`, `ChevronRightIcon`, `FolderIcon`, `FolderOpenIcon`, `ComponentFileIcon`, `CodeFileIcon`, `ConfigFileIcon`, `FileIcon`, `JsonFileIcon`, `TextFileIcon`, `ImageFileIcon`, `CssFileIcon`, `CommitsIcon`). `<Icon id="svg-…"/>` in the DOM files maps to these via `docs/research/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/source/svgs.json`.
- Hooks in `hooks.ts`: `usePrefersReducedMotion`, `useIsDesktop`, `useIsTouchDevice`, `useInView(ref, {rootMargin, threshold, once})`, `useElementSize(ref)`, `useTypewriter(lines, {charDelay, lineDelay, startDelay, enabled})` → `{visibleChars[], activeRow, done}`.
- `cn()` from `@/lib/utils` (tailwind-merge already knows the custom text sizes).
- Lenis: `useLenis` from `lenis/react` (a root Lenis is mounted by `PageShell`).

## 3. Content-driven contract (important)
The same component will render **two sites**: the CA reference page and a SAT-SA project landing page with different copy.
- The component file exports a `XxxContent` TypeScript interface (all copy, links, lists, and asset refs) and `export function XxxSection({ content }: { content: XxxContent })`. No hard-coded copy in the component; generic affordance labels may be defaults inside `content`.
- Put the CA content, **verbatim** from the DOM file, in the named content file, exporting a typed constant.
- Keep interfaces general, e.g. lists of `{ label, href, pulse? }`. Avoid CA-only assumptions such as "exactly 2 editions" (render N; lay out 2 columns on lg).

## 4. Rules
- TypeScript strict, no `any`, named exports, PascalCase components, 2-space indent, `"use client"` only where needed.
- Tailwind classes only. Inline `style` is allowed only for dynamic values (computed transforms, delays) or things with no utility (clip-path paths, CSS variables).
- Only create or modify **your own files** (listed in your task). Do not touch `src/app/**`, `globals.css`, other sections, or `shared/*` (except the scene file you own, for B1/B2).
- Images: plain `<img>` is fine (add an eslint-disable comment for `@next/next/no-img-element` on that line if lint complains) or `next/image` with explicit width/height. Asset paths start with `/sites/www-contentarchitecture-dev-80b3abaf/…`.
- Accessibility basics: buttons have labels, decorative things are `aria-hidden`, keep the `sr-only` text the DOM shows.

## 5. Verify and commit
- `npx tsc --noEmit` must pass and `npx eslint <your files>` must be clean.
- Commit on your worktree branch: `git add <your files> && git commit -m "feat(ca): <component>"`. **Do not add any Co-Authored-By or other trailer lines.** Do not push.
- Final report (short): files created, the exported content interface (paste it), behaviours implemented, and any deviation from the spec or primitive bug found.

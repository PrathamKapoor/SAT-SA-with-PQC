# ProblemsSection Specification (B5)

## Overview
- **Target files:** `…/root-8a5edab2/ProblemsSection.tsx` (exports `ProblemsContent` and `ProblemsSection({ content })`) and `…/root-8a5edab2/content/problems.ts` (`problemsContent`).
- **DOM reference:** `docs/research/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/dom/02-problems.html`.
- **Screenshot:** `…/design-references/…/root-8a5edab2/02-problems-1440.jpeg`.
- **Interaction model:** typewriter on viewport enter, plus a draggable window (title bar).

## Structure (copy classes verbatim)
- **Section:** `bg-off-white py-72 text-black lg:py-160` → `grid grid-cols-1 gap-x-16 gap-y-32 px-16 lg:grid-cols-12 lg:px-0`.
- **Left** `order-2 lg:order-1 lg:col-span-5 lg:pl-100` → `<DitherFrame title={content.terminalTitle} draggable>` (the frame primitive reproduces the frame, inner window and title bar). Body:
  - `div.p-16 overflow-x-auto` (add `scrollbar-thin`), holding:
    - an `sr-only` full transcript (all lines joined with values, then the summary)
    - `div[aria-hidden].flex min-w-max flex-col gap-y-2`
  - Each problem row: `div.flex items-baseline justify-between gap-x-16 whitespace-pre`, containing:
    - left `span.flex items-baseline gap-24`: number `…text-dark-grey tabular-nums` (e.g. "001") + text
    - right value `span.whitespace-pre transition-opacity duration-200` → `opacity-0` until that row finishes typing, then `opacity-100`
  - Then one empty spacer row, then the summary row (no number, no value).
  - Typewriter: type number+text of each row sequentially, then the summary line (`useTypewriter`, charDelay ≈18ms, lineDelay ≈90ms; start when the frame enters the viewport).
  - Each typed span sits over an `invisible` copy (the reserve pattern from the DOM).
  - Cursor: `span.ml-px inline-block h-[1em] w-[0.55em] translate-y-[0.15em] animate-cursor-blink bg-current align-baseline` after the current char. It stays blinking at the end of the summary.
- **Right** `order-1 flex flex-col gap-32 lg:order-2 lg:col-span-6 lg:col-start-7 lg:pr-80`, containing:
  - `h2.text-balance font-medium text-headline-10` in `Reveal`
  - paragraphs `div.w-full text-body-20 text-dark-grey > div.flex w-full flex-col gap-[1em]`, one `Reveal` div per paragraph

## Content (CA, verbatim; from the DOM sr-only text)
- terminalTitle: "Common problems"
- rows `{ num, text, value }`:
  - 001 Agent redesigns the architecture on every prompt — ∞ HRS
  - 002 Page builder schema + section registration + preview — ~5 HRS
  - 003 Draft mode + live preview + webhook revalidation — ~4 HRS
  - 004 CDN vs. data cache — stale content after publish — ~3 HRS
  - 005 Studio structure editors can actually use — ~3 HRS
  - 006 SEO metadata, OG images, sitemaps, robots.txt — ~2 HRS
  - 007 Rewriting the same 12 components — ~2 HRS
  - 008 Redirects, analytics, view transitions, Mux — ~2 HRS
  - 009 Contact form + spam guard + Resend wiring — ~1 HR
  - 010 ESLint, Prettier, Biome, git hooks — ~1 HR
  - 011 Basic auth for staging environments — ~1 HR
- summary: "ESTIMATED TIME LOST: ~24 HOURS PER PROJECT  (3 FULL DAYS)" (two spaces before the parenthesis)
- heading: "The page builder alone costs you days. Every single time."
- paragraphs: take the two paragraphs verbatim from the DOM.

## Responsive
- **Mobile:** the heading and text come first (order-1), then the terminal (order-2), both full width with px-16. The terminal scrolls horizontally.
- **Desktop:** terminal in cols 1–5 with pl-100; text in cols 7–12 with pr-80.

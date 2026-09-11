# HeroSection Specification (B4)

## Overview
- **Target files:** `…/root-8a5edab2/HeroSection.tsx` (exports `HeroContent` and `HeroSection({ content })`) and `…/root-8a5edab2/content/hero.ts` (`heroContent`).
- **DOM reference:** `docs/research/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/dom/01-hero.html`.
- **Screenshots:** `…/design-references/…/root-8a5edab2/01-hero-1440.jpeg` and `20-mobile-hero-390.jpeg`.
- **Interaction model:** entrance (time) plus scroll-cue click. The spiral is its own component.

## Structure (copy classes verbatim from the DOM file)
- **Section:** `div[data-page-builder-section] relative grid min-h-svh grid-cols-1 grid-rows-[auto_80vh] gap-x-16 bg-off-white text-black lg:grid-cols-12 lg:grid-rows-1`.
- **Text column:** `flex flex-col gap-48 px-16 pt-160 pb-48 lg:col-span-5 lg:justify-center lg:pt-64 lg:pr-0 lg:pl-80`, containing:
  - `div.my-auto`:
    - eyebrow `p.mb-20 font-mono text-caption-20 uppercase`
    - `h1.mb-32 whitespace-pre-line text-balance font-medium text-headline-20` (the title has an explicit line break: "The stack agents\ndon't reinvent.")
    - body `div.w-full text-body-20 text-dark-grey > div.flex w-full flex-col gap-[1em]` with one `div` per paragraph
    - CTA wrapper `div.block w-full mt-32` → `CaButton leftText rightText variant="dark" showPulseDot href`
  - Wrap eyebrow, h1 and paragraphs in `Reveal`, and the CTA in `Reveal rise delay={300}`.
- **Status grid** `div.hidden lg:block` → `div.font-mono text-caption-10 uppercase` with:
  - an sr-only full string
  - `div.flex flex-col gap-y-4`, with rows `div.flex flex-wrap items-baseline justify-between gap-x-16 gap-y-4`
  - each item `span.relative inline-block whitespace-pre`, containing an invisible full text plus an absolute typed overlay
  - Type all items in reading order with `useTypewriter` (charDelay ≈30ms, lineDelay ≈60ms, startDelay ≈600ms, enabled once in view).
  - The last item ends with the blinking block cursor `span.absolute top-0 left-full ml-px h-[1em] w-[0.55em] translate-y-[0.15em] animate-cursor-blink bg-current`. During typing, the cursor sits after the current char.
- **Spiral panel** `div.relative overflow-hidden bg-black lg:col-span-6 lg:col-start-7 lg:aspect-auto` → `div.size-full absolute inset-0` → `<SpiralScene phrase={content.spiralPhrase} />`.
- **Scroll cue** `button[aria-label]` with the exact classes from the DOM: `absolute bottom-40 left-[calc(50%_+_8px)] hidden -translate-x-1/2 lg:flex`, `bg-black-deep`, `ring-white/20`, and so on.
  - Inner track: `span.relative block h-48 w-6 overflow-hidden` with background `repeating-linear-gradient(to bottom, rgba(255,255,255,0.12) 0 1px, transparent 1px 8px)` (inline style allowed).
  - Moving block: `animate-hero-scroll-cue` (and a static one under `motion-reduce`).
  - onClick: `lenis.scrollTo(lenis.scroll + window.innerHeight, { duration: 1.2, easing: easeOutExpo })`, with `useLenis()` from `lenis/react` and `easeOutExpo` from `shared/SmoothScroll`. Under reduced motion use `{ immediate: true }`.
  - It fades in (opacity 0→1, 0.4s, delay 0.4s).

## Content (CA, verbatim)
- eyebrow: "Full-stack kit for Next.js and Astro."
- title: "The stack agents\ndon't reinvent."
- body: ["Frontend, Sanity schema, fetch layer, SEO, redirects, forms: six years of decisions, committed. AGENTS.md and a dozen skills load them before your first prompt, and two MCP servers let the agent check its own work."]
- cta: { leftText: "Get", rightText: "access", href: "#pricing", pulse: true }
- statusRows: [["NEXT 16.x","ASTRO 7.x","SANITY v6","TS: STRICT"],["AGENTS.MD: LOADED","MCP: 2 SERVERS","DRIFT: 0"]]
- statusLabel (sr-only): "NEXT 16.x ASTRO 7.x SANITY v6 TS: STRICT. AGENTS.MD: LOADED MCP: 2 SERVERS DRIFT: 0"
- spiralPhrase: "THE CONTENT ARCHITECTURE."
- scrollCueLabel: "Scroll to the next section"

## Responsive
- **Mobile:** the text column stacks on top (pt-160, px-16), and the spiral fills an 80vh row below. The status grid and scroll cue are hidden.
- **Desktop:** 5/12 text (vertically centred, the status grid pinned at the bottom by `justify-between` via `gap-48` and `my-auto`) and 6/12 spiral starting at column 7.

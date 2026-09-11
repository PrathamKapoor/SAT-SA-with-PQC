# ReviewsSection Specification (B9)

## Overview
- **Target files:** `…/root-8a5edab2/ReviewsSection.tsx` (exports `ReviewsContent` and `ReviewsSection({ content })`) and `…/root-8a5edab2/content/reviews.ts` (`reviewsContent`).
- **DOM reference:** `docs/research/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/dom/06-reviews.html`.
- **Screenshot:** `…/design-references/…/root-8a5edab2/07-reviews-1440.jpeg` (card 1 active and typed; card 2 shows only the blinking cursor).
- **Interaction model:** a scroll-snap carousel (drag/scroll/buttons) plus a time-driven typewriter on the active card.

## Structure (verbatim classes from the DOM)
- **Section:** `div#reviews relative isolate overflow-x-clip bg-black py-72 text-white lg:pb-160`.
- **Backdrop:** as in Showcase: `pointer-events-none absolute inset-0 -z-1` → DeferredMount → `GlyphField backgroundOnly interactive={false} entrance={false} maxFps={30}`, plus a `bg-black-deep/30` overlay.
- **Carousel:** `div[role=group][aria-label=Testimonials]` with the CSS variables from the DOM (`[--carousel-gutter:--spacing(16)] [--carousel-slide:90%] md:[--carousel-slide:55%] lg:[--c…]`; copy the full class string).
  - Track: `div.flex snap-x snap-mandatory items-stretch gap-6 motion-reduce:scroll-auto lg:gap-16` with horizontal scrolling (`overflow-x-auto`, hidden scrollbar, `data-lenis-prevent-horizontal` is fine).
  - Slides: `div[role=group][aria-label="1 of 3: Julian Fella"].min-w-0 shrink-0 grow-0 snap-center basis-[…]`. The first and last slides add the gutter to their basis; copy each exact class.
  - Card: a DitherFrame-style frame (`rounded-8 p-6 shadow-lg ring ring-black-deep … lg:p-8 bg-black-deep bg-dither`; replicate it inline, since it has no title bar), then `figure.group flex h-full min-h-300 flex-col justify-between gap-24 overflow-hidden rounded-4 bg-black …` (copy classes).
    - `blockquote > div.text-body-30 text-white lg:text-headline-10` holds the sr-only full quote, then `span.whitespace-pre-wrap` with three parts: the typed part, then the cursor `span.relative inline > span.absolute top-[0.1em] left-0 inline-block h-[1.05em] w-[0.1em] animate-cursor-blink bg-current`, then `span.text-transparent` with the remaining untyped text (this keeps the height stable).
    - `figcaption.flex items-center gap-16`:
      - avatar `div.relative size-48 shrink-0 overflow-hidden rounded-full ring-1 ring-white/15` → `AsciiImage` (32×18 grid, `className="absolute inset-0"`) with the real photo `img` stacked on top (opacity-0 → `group-hover:opacity-100`, classes from the DOM)
      - `div.min-w-0 flex-1 font-mono text-caption-10 uppercase` → `p.truncate text-white` name and `p.truncate text-dark-grey` role
- **Controls** under the track, centred, mono: `[<]`, `01 / 03` (current white, the slash and total dimmer), `[>]`. Find the exact markup and classes at the end of the DOM file.
  - Buttons scroll to the previous/next slide (`scrollTo` with smooth behaviour, snap-center). They are disabled (dimmed) at the ends.
- **No autoplay** (verified live: 10s in view, scrollLeft stayed 0). The live carousel is `blossom-carousel`, which adds **mouse drag-to-scroll** on desktop. Implement pointer drag: on pointerdown with a mouse, track the delta, set `scrollLeft`, and disable snap while dragging; on release, snap to the nearest slide with smooth scrolling. Touch uses native scrolling.
- **Active slide** = the one whose centre is nearest the track centre (scroll listener, rAF-throttled).
  - Typewriter: when a slide becomes active (and the section is in view), type its quote from 0 at ≈22ms/char. Previously typed slides stay complete.
  - Inactive, never-typed slides show only the blinking cursor followed by the transparent text.
  - Reduced motion: show the full quotes.

## Content (CA, verbatim from the DOM)
- label: "Testimonials"
- items (the quotes include the curly quotes):
  - Julian Fella · Co-Founder, Good Fella · grid `julian-fella` · photo `/sites/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/avatars/julian-fella.png`
  - Elliott Mangham · Founder & Frontend Engineer · grid `elliott-mangham` · `…/avatars/elliott-mangham.png`
  - Malik Kotb · (role from DOM) · grid `malik-kotb` · `…/avatars/malik-kotb.png`
- Copy the full quote text for each from the DOM sr-only spans.
- glyph: `{ model: decodeGlyphFieldModel(orb-model.json), phrase: glyph-phrases.json → phrases.reviews }`.
- Item type: `{ quote: string; name: string; role: string; avatar: { ascii: AsciiGrid; src: string } }`.

## Responsive
Slide width is 90% on mobile, 55% on md, and the lg value from the DOM class. Cards stretch to equal height (`items-stretch`, min-h-300).

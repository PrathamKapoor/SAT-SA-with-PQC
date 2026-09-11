# FaqSection Specification (B11)

## Overview
- **Target files:** `…/root-8a5edab2/FaqSection.tsx` (exports `FaqContent` and `FaqSection({ content })`) and `…/root-8a5edab2/content/faq.ts` (`faqContent`).
- **DOM reference:** `docs/research/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/dom/08-faq.html`.
- **Screenshot:** `…/design-references/…/root-8a5edab2/09-faq-1440.jpeg`.
- **Interaction model:** click-driven accordion. The heading column is sticky on lg.

## Structure (copy classes verbatim)
- **Section:** `div#faq relative isolate bg-black px-16 py-72 text-white lg:px-80 lg:py-160`.
- **Backdrop:** as in Showcase: DeferredMount → `GlyphField backgroundOnly interactive={false} entrance={false} maxFps={30}` with the `faq` phrase, plus a `bg-black-deep/30` overlay.
- **Grid** `div.grid grid-cols-1 gap-x-16 gap-y-64 lg:grid-cols-12 lg:gap-y-32`:
  - **Left** `div.contents lg:sticky lg:top-80 lg:col-span-4 lg:flex lg:max-h-[calc(100svh-(--spacing(160)))…` (copy the full class string; on lg it is a sticky flex column that pushes the CTA to the bottom):
    - `h2.text-balance font-medium text-headline-10` in Reveal
    - `div.order-last lg:order-0` → `CaButton variant` (check the DOM: `*:data-text:bg-ghost-grey` → light) with leftText/rightText/href
  - **List** `ul.flex flex-col lg:col-span-7 lg:col-start-6`. Each `li.border-white/15 border-b` holds:
    - `h3 > button.group flex w-full cursor-pointer items-center justify-between gap-24 py-24 text-left font-…` (copy the classes) with `aria-expanded` and `aria-controls` pointing to the panel id
      - left: `span.text-dark-grey` "Q.{num} /" + `span` question (mono caption uppercase per the DOM classes)
      - right: a 24px square `span.relative grid size-24 shrink-0 place-items-center rounded-2 bg-white/10 transition-colors …` with a horizontal bar and a vertical bar. When open, the vertical bar scales to 0 (the `+` becomes `−`), with a 200ms transform transition.
    - Panel `div.overflow-hidden` (`id`, `role="region"`, `aria-labelledby`) → `div.w-full pb-24 text-body-20 text-ghost-grey > div.flex w-full flex-col gap-[1em]`, one div per paragraph.
    - Open/close animates height (a CSS grid-rows `0fr → 1fr` trick or measured height, ~300ms ease-out) with opacity.
- **Behaviour:** one open at a time (clicking another closes the previous; clicking the open one closes it). Item 0 is open initially.

## Content (CA, verbatim from the DOM)
- title: "Before you buy"
- cta: `{ leftText: "Get", rightText: "access", href: "#pricing" }`
- items: every Q/A in DOM order (Q.001 "What stack is this built on?" … the last item). Answers are verbatim, split into paragraphs where the DOM has multiple `div.empty:h-[1lh]`.
- glyph: `{ model: decodeGlyphFieldModel(orb-model.json), phrase: glyph-phrases.json → phrases.faq }`
- Item type: `{ question: string; answer: string[] }`; numbering is automatic (`Q.001`).

## Responsive
- **Mobile:** stacked. Heading, list, then the CTA last (`order-last`).
- **Desktop:** a sticky left column (4/12) with the CTA pinned at the bottom of the viewport-height column; the list sits in columns 6–12.

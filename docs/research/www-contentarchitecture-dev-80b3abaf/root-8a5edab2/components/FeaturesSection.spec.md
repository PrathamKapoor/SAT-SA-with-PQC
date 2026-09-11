# FeaturesSection Specification (B6)

## Overview
- **Target files:** `…/root-8a5edab2/FeaturesSection.tsx` (exports `FeaturesContent` and `FeaturesSection({ content })`) and `…/root-8a5edab2/content/features.ts` (`featuresContent`).
- **DOM reference:** `docs/research/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/dom/03-features.html`.
- **Screenshots:** `…/design-references/…/root-8a5edab2/03-features-a-1440.jpeg` and `04-features-b-1440.jpeg`.
- **Interaction model:** scroll (a sticky WebGL backdrop while the list scrolls past) plus pointer (the GlyphField handles hover and click itself).

## Structure (classes verbatim from the DOM)
- **Section:** `div#features relative isolate min-h-svh pt-72 pb-64 text-white lg:py-160` (`id` from `content.id`, default "features").
- **Backdrop** `div.absolute inset-0 -z-1`:
  - `DeferredMount className="size-full lg:sticky lg:top-0 lg:h-svh" placeholder={<div className="size-full bg-black" />}` → `<GlyphField model={content.glyph.model} phrase={content.glyph.phrase} modelLayout={isDesktop ? "right" : "bottom"} modelMaxWidth={isDesktop ? 0.55 : 1} />`, using `useIsDesktop()` from shared hooks.
  - Sibling overlay `div.pointer-events-none absolute inset-0 bg-black-deep/30`.
- **Foreground** `div.pointer-events-none grid grid-cols-1 gap-16 px-16 lg:grid-cols-12 lg:px-80` → `div.lg:col-span-5`, containing:
  - `div.flex flex-col gap-32`:
    - `h2.pointer-events-auto whitespace-pre-line text-balance font-medium text-headline-10`, in Reveal. The title contains "\n".
    - intro `div.w-full pointer-events-auto text-body-20 text-ghost-grey > div.flex w-full flex-col gap-[1em]`, one Reveal per paragraph.
  - `ul.col-span-12 mt-80 flex flex-col gap-64`, one `li` per item with class `pointer-events-auto flex flex-col gap-12 lg:max-w-1/2` plus the zigzag margin `lg:ml-0 | lg:ml-[20%] | lg:ml-[40%]` by `index % 3`. Each `li` holds:
    - `h3.font-mono text-caption-20 uppercase` → `"{num} / {title}"` (the DOM renders "001", "/", title; copy the exact inner spans and colours from the DOM file)
    - `p.whitespace-pre-line text-body-10 text-ghost-grey` (body)
    - Wrap the h3 and p each in `Reveal`.
- **pointer-events:** the foreground is `pointer-events-none`, with text blocks re-enabled (`pointer-events-auto`), so the WebGL field under empty space stays hoverable and clickable. Keep this exactly.

## Content (CA, verbatim from the DOM)
- title: "Every decision already made.\nSo you can skip to the actual work."
- intro: one paragraph starting "The production foundation under my client work: hundreds of decisions, schema, fetching, structure, SEO, deployment, made once over six years and committed. Clone it, rename it, ship. …". Copy the full text from the DOM (join the split lines with spaces).
- items: 9 × `{ num: "001", title, body }`. Titles: Agent-native · Agent-ready in production · Schema as a system · The hard fields, already built · Fetch layer, solved · A Studio editors actually use · SEO, done not deferred · Production-ready from day one · (the 9th from the DOM). Copy each body verbatim from the DOM (join split lines).
- glyph:
  - `model`: `decodeGlyphFieldModel(orbModel)`, where `orbModel` is imported from `../data/orb-model.json` and `decodeGlyphFieldModel` comes from `../shared/glyph-model`. The relative path from content/ is `../data/orb-model.json`; from shared it is `@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/glyph-model`.
  - `phrase`: `glyphPhrases.phrases.features`, from `../data/glyph-phrases.json`.
  - Type it as `{ model: GlyphFieldModel; phrase: string }`.

## Responsive
- **Mobile:** single column. The GlyphField backdrop is NOT sticky (absolute inset-0, full section height) and puts its model at the bottom. The list has no zigzag (`ml-0`).
- **Desktop:** the text column is 5/12 wide; the backdrop is sticky at 100svh while the ~2,800px section scrolls.

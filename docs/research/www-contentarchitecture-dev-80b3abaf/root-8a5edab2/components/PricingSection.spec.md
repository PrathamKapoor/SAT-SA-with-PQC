# PricingSection Specification (B10)

## Overview
- **Target files:** `…/root-8a5edab2/PricingSection.tsx` (exports `PricingContent` and `PricingSection({ content })`) and `…/root-8a5edab2/content/pricing.ts` (`pricingContent`).
- **DOM reference:** `docs/research/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/dom/07-pricing.html`.
- **Screenshot:** `…/design-references/…/root-8a5edab2/08-pricing-1440.jpeg` (the includes panel continues below the fold).
- **Interaction model:** mostly static. The price digit reels roll to their value on viewport enter; buttons hover with the odometer.

## Structure (copy classes verbatim)
- **Section:** `div#pricing bg-off-white py-72 text-black lg:py-160` → `div.grid grid-cols-1 gap-x-16 gap-y-64 px-16 lg:grid-cols-12 lg:px-80`.
- **h2** `whitespace-pre-line text-balance font-medium text-headline-10 lg:col-span-6 …` (3 lines, "\n"-separated), in Reveal.
- **Trusted row** `div.group flex items-center gap-12 lg:col-span-6 lg:col-start-7 lg:row-start-1 …`:
  - avatars: the first in `div.relative`, the rest in `div.relative -ml-10`; each `img.size-32 shrink-0 rounded-full bg-mid-grey object-cover outline outline-black/20 …` (copy the class, including any hover/transition bits)
  - label `p.font-mono text-caption-10 text-dark-grey uppercase`
- **Editions** `div.grid grid-cols-1 gap-16 lg:col-span-12 lg:row-start-2 lg:grid-cols-2`. Each edition is `div.relative isolate flex h-full flex-col text-white` made of 3 stacked blocks joined by `div.flex justify-center > div.h-4 border-x border-black` (copy the exact join markup, which may carry width classes):
  1. **Price block** `div.flex flex-col gap-12 p-16 lg:p-32 rounded-8 bg-black`:
     - a top row with the edition tag chip (left) and the status chip (right, `PulseDot` + "Available now")
     - the price row: a big price `span.inline-flex text-headline-20 leading-none`, then a compare-at price in `font-mono text-caption-10` with a strike line `span.pointer-events-none absolute inset-x-0 top-1/2 h-px bg-current`, then an optional third mono element (see the DOM)
  2. **Spec list** `ul.flex flex-1 flex-col gap-4 p-16 font-mono text-caption-10 uppercase lg:p-32 rounded-8 bg-black`, with `li.flex gap-24` → `span.text-dark-grey tabular-nums` num + `span.text-ghost-grey` text
  3. **CTA block** `div.flex flex-col gap-12 rounded-8 bg-black p-16 lg:p-32` → `CaButton variant="light" leftText rightText href`, plus any extra line in the DOM
- **Price reel:** each digit is `span.relative inline-block overflow-hidden align-baseline`, containing `span.invisible` (the target digit) and `span.absolute inset-x-0 top-0 flex flex-col` with a column of 0–9.
  - On viewport enter, translate the column to `-{digit}em`, which needs `leading-[1em]` rows. Use transition 900ms with ease `cubic-bezier(0.23,1,0.32,1)` and a per-digit delay of 60ms.
  - The currency symbol stays static. Keep the `sr-only` full price. Reduced motion: no transition.
- **Includes panel** `div.flex flex-col gap-16 rounded-8 bg-black p-16 text-white lg:col-span-12 lg:row-start-3 lg:p-32`:
  - title `span.font-mono text-caption-10 text-dark-grey uppercase`
  - `ul.font-mono text-caption-10 uppercase lg:columns-2 lg:ga…` (copy the classes), with numbered items `001…`

## Content (CA, verbatim from the DOM)
- title: "Two editions.\nOne architecture.\nLifetime updates."
- trusted:
  - avatars: `/sites/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/avatars/trusted-{goodfellastudio,minhchanh6,elliottmangham,malikkotb,studioboldest}.png`, in DOM order
  - label: "trusted by 40+ engineers"
- editions: `[{ tag: "Next.js", status: "Available now", price: "€399", compareAt: "€549", specs: ["THE NEXT.JS 16 + SANITY V6 REPO", "…"], cta: { leftText: "Get", rightText: "access", href: "https://www.contentarchitecture.dev/checkout?plan=next&code=ASTROLAUNCH" } }, { tag: "Astro", … }]`. Copy every string from the DOM.
- includes: `{ title: "Every edition includes", items: [ …all numbered items from the DOM… ] }`.
- Model `price` as `{ currency: "€", amount: "399" }` so the reels know the digits. The same applies to compareAt.

## Responsive
- **Mobile:** single column. The title comes first, then the trusted row, the editions stacked, and the includes panel with one column.
- **Desktop:** the title (cols 1–6) and trusted row (cols 7–12, right-aligned and bottom-aligned per the DOM classes) share row 1; editions are 2 columns in row 2; includes span row 3.

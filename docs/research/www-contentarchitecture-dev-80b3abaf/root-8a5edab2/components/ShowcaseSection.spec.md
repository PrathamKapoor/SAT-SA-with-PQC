# ShowcaseSection Specification (B8)

## Overview
- **Target files:** `…/root-8a5edab2/ShowcaseSection.tsx` (exports `ShowcaseContent` and `ShowcaseSection({ content })`) and `…/root-8a5edab2/content/showcase.ts` (`showcaseContent`).
- **DOM reference:** `docs/research/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/dom/05-showcase.html`.
- **Screenshot:** `…/design-references/…/root-8a5edab2/06-showcase-1440.jpeg`.
- **Interaction model:** hover (desktop: the ASCII card reveals the real screenshot), plus scroll position (mobile: the centred card becomes active).

## Structure (verbatim classes)
- **Section:** `div#showcase relative isolate bg-black px-16 py-72 text-white lg:px-80 lg:py-160`.
- **Backdrop:** `div.pointer-events-none absolute inset-0 -z-1` (background `#232323`) → `DeferredMount` → `<GlyphField model phrase backgroundOnly interactive={false} entrance={false} maxFps={30} />`, plus `div.absolute inset-0 bg-black-deep/30`.
- **Header** `div.mb-80 flex flex-col gap-16`:
  - `h2.text-balance font-medium text-headline-10` in Reveal
  - `div.w-full max-w-600 text-body-20 text-ghost-grey` → intro paragraph(s) with inline links `a.underline decoration-from-font decoration-dashed underline-offset-3`, opening in a new tab
  - Model the intro as rich-ish content: `intro: Array<string | { text: string; href: string }>` (segments), rendered inline.
- **Grid** `div.grid grid-cols-1 gap-x-24 gap-y-32 lg:grid-cols-2 lg:gap-y-64`. Per item, `a.group block` (href, new tab) with `data-active` for mobile, containing:
  - `div.relative w-full mb-12`, aspect ratio 16:9 via `aspect-video` (the DOM uses inline aspectRatio 1.7778):
    - `<AsciiImage {...grid} label={label} className="absolute inset-0" />`
    - `<img className="max-w-full pointer-events-none absolute inset-0 size-full object-cover opacity-0 transition-opacity duration-500 ease-out group-hover:opacity-100 group-data-[active=true]:opacity-100 motion-reduce:transition-none" aria-hidden alt>`. Copy the exact class string from the DOM.
  - `h3.font-mono text-caption-20 uppercase` (label), in Reveal.
- **Mobile active card:** on touch/coarse pointers, set `data-active="true"` on the item whose centre is nearest the viewport centre (scroll listener, rAF-throttled). Only on `(pointer: coarse)`; on desktop, hover handles it.

## Content (CA)
- title: "The work that gets remembered."
- intro segments (verbatim, from the DOM): "Real sites, shipped on The Content Architecture. With the plumbing already handled, the effort goes where it shows. The work here has been recognized by " + link Awwwards (https://www.awwwards.com/) + ", " + link FWA (https://thefwa.com/) + ", and " + link CSSDA (https://www.cssdesignawards.com/) + ", and picked up across design directories."
- items (label, href, grid key in `../data/ascii-grids.json`, image). Images are `/sites/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/images/…`; alt text is verbatim from the DOM imgs.

| label | href | grid key | image file |
|---|---|---|---|
| Good Fella | https://good-fella.com/ | good-fella | showcase-good-fella.jpg |
| House of Honey | https://www.houseofhoney.com/ | house-of-honey | showcase-house-of-honey.jpg |
| Aspen Search | (from DOM) | aspen-search | showcase-aspen-search.jpg |
| Anuc Home | (from DOM) | anuc-home | showcase-anuc-home.jpg |
| Edoardo Lunardi | (from DOM) | edoardo-lunardi | showcase-edoardo-lunardi.jpg |
| Serve Robotics | (from DOM) | serve-robotics | showcase-serve-robotics.jpg |
| Prism | (from DOM) | prism | showcase-prism.png |
| Muralia | (from DOM) | muralia | showcase-muralia.jpg |
| blink | (from DOM) | blink | showcase-blink.jpg |
| Creative Lives in Progress | (from DOM) | creative-lives-in-progress | showcase-creative-lives.jpg |
| The Content Architecture | (from DOM) | the-content-architecture | showcase-content-architecture.png |

- glyph: `{ model: decodeGlyphFieldModel(orb-model.json), phrase: glyph-phrases.json → phrases.showcase }`.
- Item type: `{ label: string; href?: string; ascii: AsciiGrid; image: { src: string; alt: string } }`.

## Responsive
- **Mobile:** 1 column, px-16, the card nearest the centre shows its image.
- **Desktop:** 2 columns, gap-x-24, gap-y-64, px-80.

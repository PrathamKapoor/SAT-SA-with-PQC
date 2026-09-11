# BannerSection + SiteFooter Specification (B12)

## Overview
- **Target files:**
  - `…/root-8a5edab2/BannerSection.tsx` (exports `BannerContent` and `BannerSection({ content })`)
  - `…/root-8a5edab2/SiteFooter.tsx` (exports `FooterContent` and `SiteFooter({ content })`)
  - `…/root-8a5edab2/content/banner.ts` (`bannerContent`)
  - `…/root-8a5edab2/content/footer.ts` (`footerContent`)
- **DOM reference:** `docs/research/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/dom/09-banner.html` and `dom/13-footer.html`.
- **Screenshot:** `…/design-references/…/root-8a5edab2/10-footer-1440.jpeg`, which shows the banner and the partially revealed footer.
- **Interaction model:** the banner is static (draggable frame). The footer is scroll-linked (reveal parallax and overlay fade), plus a form.

## BannerSection ("calloutSection")
- **Section:** `div.bg-off-white px-16 py-72 lg:p-80` → `<DitherFrame title={content.title} draggable>`.
- **Body:** `div.p-16 @container overflow-hidden` → `<pre role="img" aria-label={content.label} className="m-0 w-full overflow-hidden whitespace-pre leading-none">`.
  - Font size is `calc(100cqw / {N})`, where N = `(longest line length) × 0.6`. The DOM uses 82.80 for its 138-char lines, so derive N from the art. A dynamic inline style is allowed.
  - The `<pre>` text is `content.art`: copy the figlet art from the DOM **exactly**, preserving every space and backslash. Use a template literal and escape backslashes and backticks correctly.
- **Content:** `title: "The content architecture"`, `label: "The next 3 days\nare yours."`, and `art` (verbatim).

## SiteFooter (sticky reveal)
- **Root:** `<footer className="sticky bottom-0 z-0 overflow-hidden bg-black px-16 py-72 text-white lg:p-80">`.
- **Backdrop:** `div.pointer-events-none absolute inset-0 -z-1` (bg #232323) → DeferredMount → `GlyphField backgroundOnly interactive={false} entrance={false} maxFps={30}` with `content.glyph`, plus a `bg-black-deep/30` overlay.
- **Parallax wrapper:** `div.will-change-transform`. While the footer is being uncovered, translate it from `translateY(40% of the footer height)` down to 0. The DOM showed `translate3d(0, 133.2px, 0)` when ~70% covered.
  - Progress `p` = how much of the footer is visible: `(viewportBottom - footerTop) / footerHeight`, clamped 0–1. Compute it with a scroll listener or `useLenis`.
  - Content transform: `translateY((1 - p) * 0.4 * footerHeight px)`.
  - Top overlay `div.pointer-events-none absolute inset-0 bg-black will-change-[opacity]` with `opacity: (1 - p) * 0.7`.
- **Inside** `div.flex flex-col justify-between gap-32 lg:gap-64`:
  - Top row `div.flex flex-col gap-32 lg:flex-row lg:items-start lg:justify-between lg:gap-64`:
    - **Form column** `div.flex w-full flex-col gap-16 lg:max-w-md` → `form.flex w-full min-w-0 flex-col gap-12` (noValidate) with a label (sr-only "Email") and `div.flex gap-4 lg:flex-row`, containing:
      - the email input (copy its exact class string from the DOM, `bg-black lg:flex-1`)
      - `CaButton type="submit" variant="light" leftText="Stay" rightText="updated" className="shrink-0"`
    - On submit, `preventDefault` and show an inline status line (mono caption-10): `content.newsletter.successMessage` if the email matches a basic regex, otherwise `content.newsletter.errorMessage`. There is no network call.
    - **Footer nav** `nav[aria-label=Footer].flex flex-col gap-y-12 lg:items-end`, with links `a.[--odometer-progress:0] motion-safe:hover:[--odometer-progress:1] inline-flex items-center gap-8 font-mono text-caption-20 uppercase transition-colors hover:text-current` → `<Odometer text>` plus an optional pulse dot (`span.relative flex size-6` variant from the DOM).
  - Bottom `div.flex flex-col gap-24`:
    - divider `div.h-px w-full bg-current/10`
    - `div.flex flex-col gap-4`: `p.font-mono text-caption-20 uppercase` "© <span class='inline-block w-[4ch] tabular-nums'>{year}</span> {owner}", then the credit link `a.w-fit font-mono text-caption-10 uppercase opacity-50 transition-opacity hover:opacity-100`

### Footer content (CA)
- newsletter:
  - `{ label: "Email", placeholder: "your@email.com", leftText: "Stay", rightText: "updated" }`
  - `successMessage: "Thanks — you're on the list."` and `errorMessage: "Enter a valid email address."` (the clone's own copy; the original posts to a server action)
- links:
  - Blog → https://www.contentarchitecture.dev/blog
  - Roadmap → https://www.contentarchitecture.dev/roadmap
  - Get access (pulse) → #pricing
  - Privacy Policy → https://www.contentarchitecture.dev/legal/privacy-policy
  - Terms Of Service → https://www.contentarchitecture.dev/legal/terms-of-service
  - Imprint → https://www.contentarchitecture.dev/legal/imprint
- copyright: `{ year: "2026", owner: "The Content Architecture" }`
- credit: `{ label: "Built by edoardolunardi.dev", href: "https://edoardolunardi.dev" }`
- glyph: `{ model: decodeGlyphFieldModel(orb-model.json), phrase: glyph-phrases.json → phrases.faq }` (the footer reused a phrase field; the faq phrase is fine)

## Responsive
- **Mobile:** the form stacks above the nav (left-aligned).
- **Desktop:** the form is on the left (max-w-md) and the nav is right-aligned.
- The banner figlet scales with container width via cqw.

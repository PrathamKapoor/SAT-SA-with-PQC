# SiteNav Specification (B3)

## Overview
- **Target files:** `src/components/sites/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/SiteNav.tsx` (exports `SiteNavContent` and `SiteNav({ content })`), plus the CA content in `…/root-8a5edab2/content/nav.ts` (`export const navContent: SiteNavContent`).
- **DOM reference** (exact classes): `docs/research/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/dom/00-header.html`.
- **Screenshots:** desktop `…/design-references/…/root-8a5edab2/02-problems-1440.jpeg` (idle, over off-white) and `03-features-a-1440.jpeg` (active "FEATURES" tab); mobile `20-mobile-hero-390.jpeg` (closed) and `21-mobile-menu-open-390.jpeg` (open).
- **Interaction model:** scroll-driven active tab (scroll-spy), hover (odometer), click (mobile menu toggle).

## Structure
- `<header class="pointer-events-none fixed inset-x-0 top-0 z-4 flex justify-start p-8 lg:justify-center lg:p-16">` → `<nav aria-label="Primary">` → the frame `div.rounded-8 p-6 … lg:p-8 bg-black-deep pointer-events-auto` with the dither background (use class `bg-dither` instead of the inline style).
- **Desktop panel** (`hidden … lg:flex`): a `ul` containing:
  - the logo `li` (`LogoMark` size-30, `aria-label="Home"`, links to `content.homeHref`)
  - one `li` per link with an `<a>` carrying the exact odometer classes, `text-white/55 hover:text-white`, and `<Odometer text>`
  - if `pulse`, a `PulseDot` with `absolute top-6 right-6`
  - Below the list, the 18px ghost-grey marquee strip (`h-18 … bg-ghost-grey font-mono text-black text-ui uppercase`) scrolling `content.marquee` (repeat the item; animation-duration ≈ 14.76s). Use the `Marquee` primitive; items are `px-[1em]` with `whitespace-nowrap`.
- **Active tab (scroll-spy):** each desktop `li` has an absolutely positioned highlight `span.pointer-events-none absolute inset-0 rounded-2 bg-white/8 ring-1 ring-white/15`. Only the active link's highlight is visible, and it animates between links (opacity/scale in ≈200ms; a shared layout slide is a plus but optional).
  - The active link also turns `text-white`.
  - Active section = the last `content.links[i].sectionId` whose element top ≤ 40% of the viewport height. Update on scroll (rAF-throttled); none is active above the first section.
- **Mobile panel** (`lg:hidden`): a `div.flex w-fit min-w-160 flex-col overflow-hidden rounded-4 bg-black p-4 ring-1 ring-white/10` containing:
  - a row: logo (size-24) | `button` "Menu" with a 24px `+` square (`aria-expanded`, `aria-label` "Open menu"/"Close menu"). The vertical bar rotates/scales to 0 when open, so `+` becomes `−`.
  - When open, a vertical list of the links (mono caption-10 uppercase, white/55 → white, `py-6`, pulse dot inline after PRICING), then the marquee strip `mt-4`. The open/close uses a height + opacity transition (≈300ms).
  - Clicking a link closes the menu.

## Content (CA, verbatim)
- `homeHref`: "/reference/contentarchitecture". Rewrite CA's "/" and "/#x" hrefs to "#x" so anchors work inside the reference route.
- `logoLabel`: "Home".
- `links`:
  - Features → `#features`
  - The repo → `#the-repo`
  - Showcase → `#showcase`
  - Pricing → `#pricing` (pulse)
  - FAQ → `#faq`
  - Blog → `https://www.contentarchitecture.dev/blog` (external, no sectionId)
- `marquee`: "Now available with Astro".
- `logo`: let the content choose between the built-in `LogoMark` and a custom node, e.g. `logo?: ReactNode` with `LogoMark` as the default. The SAT-SA site will pass its own mark.

## Interface guidance
`SiteNavContent { homeHref; logoLabel; logo?: ReactNode; links: { label: string; href: string; sectionId?: string; pulse?: boolean; external?: boolean }[]; marquee: string; }`

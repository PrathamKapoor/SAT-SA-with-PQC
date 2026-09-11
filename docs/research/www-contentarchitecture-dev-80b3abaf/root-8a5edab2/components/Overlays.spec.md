# Minimap + LearnMore (README drawer) Specification (B13)

## Overview
- **Target files:**
  - `…/root-8a5edab2/Minimap.tsx` (exports `Minimap({ label? })`)
  - `…/root-8a5edab2/LearnMore.tsx` (exports `LearnMoreContent` and `LearnMore({ content })`; it includes the drawer, and you may split the drawer into `ReadmeDrawer.tsx`)
  - `…/root-8a5edab2/content/learn-more.ts` (`learnMoreContent`)
- **DOM reference:** `dom/10-minimap.html`, `dom/11-learn-more.html` and `dom/12-readme-drawer.html` (under `docs/research/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/`).
- **Screenshots:** any desktop screenshot shows the minimap (top-right) and the widget (bottom-right); `11-drawer-open-1440.jpeg` shows the drawer open.
- **Interaction model:** the minimap is time-driven (scan) and scroll-linked (thumbnail offset). The widget and drawer are click-driven dialogs.

## Minimap
- Copy the DOM wrapper classes exactly: `group fixed top-8 right-8 z-3 aspect-video h-44 lg:top-16 lg:right-16 lg:h-54`, and the inner `rounded-3 bg-black/50 ring-1 ring-white/15 ring-inset backdrop-blur-sm`, etc.
- **Thumbnail:** the original draws a 96px-wide canvas snapshot of the page that translates with scroll. Implement a lightweight version:
  - On mount (and on resize), build a 96px-wide canvas representing the page. For each `main > *` section, draw a rect scaled by `96/document.documentElement.scrollWidth`, filled with the section's computed background colour (off-white or #232323), plus a few 1px light bars for its headings.
  - Place it in the two `absolute top-0 left-0 will-change-transform` layers, translated by `-(scrollY * scale)` so the minimap window follows the viewport (the minimap box is the viewport).
- **Scan layer:** keep the exact DOM:
  - `animate-minimap-scan`
  - the masked `animate-minimap-scan-counter` copy
  - the `to-accent/20` gradient
  - the `h-px bg-accent` line
  - the two 4px accent dots
- **Hover:** accent ring plus the "Inspect ↗" tooltip (`group-hover:block`). The original's button opens Studio mode; render the `button` with `aria-label={label ?? "Page overview"}` and **no action** (or scroll to top on click). It is decorative.

## LearnMore widget (fixed bottom-right)
- Copy the button classes from `dom/11-learn-more.html`: a `data-label` pill "Learn more" (odometer), a horizontal `Connector` (length 28, inside `span.flex w-48 justify-center`), and a `data-icon` 48px "+" square.
- Wrapper: `fixed right-8 bottom-8 z-4 lg:right-16 lg:bottom-16`.
- Set `aria-haspopup="dialog"` and `aria-expanded`, and open the drawer on click.

## README drawer (dialog)
- Portal to `document.body` via `createPortal` from react-dom (render only after mount). Structure:
  - **Backdrop:** a fixed inset-0 `bg-black/40` that fades in (300ms). Clicking it closes the drawer.
  - **Dialog container:** `fixed inset-y-0 right-0 z-[60] flex w-full justify-end p-8 lg:p-16 pointer-events-none`. It slides in from the right (translateX(100%) → 0, 500ms `cubic-bezier(0.23,1,0.32,1)`), then holds the dialog element.
  - **The dialog element** (from the DOM): `role="dialog" aria-modal="true" aria-labelledby tabIndex={-1}`, classes `pointer-events-auto relative isolate flex h-full w-full flex-col overflow-hidden p-8 text-black outline-none lg:max-w-960 lg:flex-row lg:p-16`. It contains:
    - **TOC nav** `nav[aria-label=Sections].w-full rounded-8 bg-mid-grey p-16 font-mono text-caption-10 uppercase lg:max-w-182`: buttons with odometer text (truncated with "…" as in the DOM), `text-dark-grey hover:text-black`. The active section is `text-black`. Clicking scrolls the content panel to that section (smooth).
    - Connectors: a horizontal one (mobile, bottom-left) and a vertical one (lg, top-24 right-0) in `text-mid-grey`, joining the TOC to the panel.
    - **Content panel** `div.min-h-0 overflow-y-auto overscroll-none rounded-8 bg-mid-grey`. Add `data-lenis-prevent` so wheel events scroll the panel, not the page. Inside:
      - header: `h2` (id for aria-labelledby, `font-mono text-body-20 uppercase`) "README / The content architecture", a subtitle `p.mt-12 font-mono text-caption-20 text-dark-grey uppercase`, and the **Close** button (label pill "Close" + connector + "X" square, same button recipe as the widget)
      - sections `section#{id}.flex flex-col gap-16 pb-64 last:pb-0`, in a `divide-y divide-black/20` column: `h3.font-mono text-caption-20 uppercase` plus paragraphs (`text-body-10`, `flex flex-col gap-[1em]`)
      - The "Who am I" section contains an inline portrait `img.inline-flex h-[1em] w-auto translate-y-[-0.1em] …` (copy the classes) within a paragraph. Model it as a paragraph segment `{ image: { src, alt } }`.
- **Behaviour:**
  - On open: lock page scroll (`document.documentElement.dataset.scrollLocked = ""`, and `lenis.stop()` via `useLenis`), then focus the dialog.
  - On close (Esc, backdrop, Close button): restore scroll (`lenis.start()`) and return focus to the trigger.
  - The TOC highlights the section in view within the panel (IntersectionObserver with root = panel).

## Content (CA, verbatim from the drawer DOM)
- trigger: "Learn more"
- title: "README / The content architecture"
- subtitle: "A personal note from the maintainer"
- close: "Close"
- sections: `[{ id: "why-this-exists", number: "001", title: "Why this exists", paragraphs: [...] }, { id, "002", "Why I keep shipping it", ... }, { "003", "Who am I", ... }]`. Copy all paragraph text from the DOM, joining split lines into full paragraphs.
- portrait: `/sites/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/avatars/maintainer.jpg`, with its alt verbatim.
- Types:
  - paragraph = `Array<string | { image: { src: string; alt: string } } | { text: string; href: string }>`
  - section = `{ id; number; title; paragraphs: Paragraph[] }`

## FloatingCapture (newsletter popup): added in the 2026-09-12 recon
- **Target files:**
  - `…/root-8a5edab2/FloatingCapture.tsx`: exports `FloatingCaptureContent` and `FloatingCapture({ content })`
  - `…/root-8a5edab2/content/floating-capture.ts`: exports `floatingCaptureContent`
- **Screenshot:** none saved. It is a 520px black card at the bottom-left of the desktop viewport, above everything.
- **Interaction model:** time-driven, then click and keyboard.
  - It appears once per browser session, **12s after load** (`delaySeconds: 12`).
  - It is skipped if the session cookie `tca-prompt-site=1` or `tca-captured=1` exists. Set `tca-prompt-site=1; path=/; SameSite=Lax` at the moment it shows.
  - Exit-intent is off on CA (`exitIntent: false`). Keep an `exitIntent?: boolean` prop that, when true, also opens it on `document.documentElement` `mouseleave`.
  - Esc, or the X button, closes it. After a successful subscribe it closes itself 4s later.
- **Exact DOM:**
  ```
  <div role="dialog" aria-label={title} class="fixed inset-x-16 bottom-16 z-50 lg:inset-x-auto lg:bottom-48 lg:w-520 lg:left-48">   ← side "left" (right: lg:right-48)
    <section aria-labelledby={id} class="flex flex-col gap-16 rounded-8 p-16 lg:gap-24 lg:p-32 border border-white/20 bg-black text-white shadow-2xl">
      <div class="grid gap-16">
        <div class="flex flex-col gap-8">
          <div class="flex items-start justify-between gap-16">
            <p id={id} class="text-balance font-medium text-body-30">{title}</p>
            CLOSE BUTTON
          </div>
          <p class="text-pretty text-body-10 text-ghost-grey">{text}</p>
        </div>
        <EmailCapture copy={content.form} buttonVariant="light" onSuccess={…close after 4000ms…} />
  ```
- **CLOSE BUTTON** (CA "IconButton", small, label hidden): `<button type="button" aria-label="Close">` with classes, verbatim:
  `inline-flex w-fit min-w-0 shrink-0 cursor-pointer items-end whitespace-nowrap font-mono text-caption-10 uppercase [--odometer-progress:0] motion-safe:hover:[--odometer-progress:1] disabled:pointer-events-none disabled:opacity-50 disabled:grayscale *:data-label:inline-flex *:data-label:items-center *:data-label:justify-center *:data-label:rounded-4 *:data-icon:inline-flex *:data-icon:items-center *:data-icon:justify-center *:data-icon:rounded-4 *:data-connector:transition-colors *:data-icon:transition-colors *:data-label:transition-colors *:data-icon:size-32 *:data-label:h-18 *:data-connector:w-32 *:data-label:px-6 *:data-icon:bg-ghost-grey *:data-label:bg-ghost-grey *:data-connector:text-ghost-grey *:data-icon:text-black *:data-label:text-black [&:hover_[data-connector]]:text-white [&:hover_[data-icon]]:bg-white [&:hover_[data-label]]:bg-white flex-col-reverse -mt-4 -mr-4`
  It has a single child, `<span data-icon="true">X</span>`.
  - The same hover recipe (`[&:hover_[data-icon]]:bg-white`, `[&:hover_[data-label]]:bg-white`, `[&:hover_[data-connector]]:text-white`, plus the three `transition-colors`) also applies to the **LearnMore** widget and the drawer **Close** button above. The condensed DOM files omit these hover classes, so add them.
- **Motion** (render only after mount; `AnimatePresence`-like, implemented with CSS transitions and a mounted/visible state pair):
  - enter from `opacity:0; translateY(24px)` → `opacity:1; translateY(0)`, 500ms ease-out
  - exit to `opacity:0; translateY(24px)`, 350ms ease-in-out, then unmount
  - Reduced motion: 10ms.
- **Content (CA, verbatim):**
  - `title: "Not buying today? Stay close."`
  - `text: "One short email when the repo changes or a discount goes live. Nothing else, unsubscribe anytime."`
  - `delaySeconds: 12`, `side: "left"`, `exitIntent: false`, `closeLabel: "Close"`
  - `form: { label: "Email", placeholder: "your@email.com", ctaText: "Subscribe", successMessage: "You're on the list.", errorMessage: "Enter a valid email address." }` (type `EmailCaptureCopy` from `shared/EmailCapture`)
- **Responsive:** mobile is full-width with 16px insets at the bottom. On lg it is 520px wide, 48px from the left and bottom.

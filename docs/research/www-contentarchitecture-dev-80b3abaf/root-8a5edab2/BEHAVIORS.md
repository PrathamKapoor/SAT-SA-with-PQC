# contentarchitecture.dev — Behaviors

Captured 2026-09-11 with Chrome DevTools MCP (claude-in-chrome was not connected). Viewports used: 1440×900, 768×1024, and 390×844 (mobile + touch emulation).
Stack: Next.js (Turbopack) + Tailwind v4, **Lenis** smooth scroll, motion/react, OGL (WebGL2) for two canvas scenes, `marqy` marquee, `blossom-carousel`.
Source of truth for exact class strings: `dom/*.html` (condensed live DOM). Tokens: `source/site.css`.

## Global
| Behavior | Trigger | Detail |
|---|---|---|
| Smooth scroll | always | Root `ReactLenis`: `lerp 0.1` (default), `allowNestedScroll: true`, anchors `{duration: 1.2, easing: easeOutExpo}`. `html.lenis` class is present. |
| Odometer hover text | hover an ancestor with `[--odometer-progress:0] motion-safe:hover:[--odometer-progress:1]` | Each char is a column `[char, 4 random glyphs A–Z0–9, char]` that moves `translateY(-5em)`. Duration 520ms; delay `index × 28ms`; easing `cubic-bezier(0.23,1,0.32,1)`. Used on buttons, nav links, drawer TOC, and footer links. |
| Split-line entrance | element enters viewport (first load ≈1.2s after nav) | `data-split="lines"` text: each line fades opacity 0→1 over ≈1s with ease-out. Lines are masked (`clip-path: inset(-0.25em 0)`) during the entrance and the mask is removed afterwards. Implemented as `Reveal` (whole block). |
| CTA entrance | viewport enter, ≈300ms after text | opacity 0→1 plus translateY 48px→0, ≈1s ease-out. `Reveal rise`. |
| Typewriter | viewport enter | Hero status grid, Problems terminal, and the Reviews quote type char-by-char (≈30ms/char). An invisible copy reserves layout. A block cursor `h-[1em] w-[0.55em] translate-y-[0.15em] animate-cursor-blink bg-current` follows the last char, and stays blinking on the final line. |
| Focus ring | keyboard focus | 2px inset ring in `accent` (#ff9100). Rule in base layer. |
| Selection | select text | `::selection { background-color: currentColor }` |
| Footer reveal | scroll to end | `<main>` is `relative z-1`; footer is `sticky bottom-0 z-0` underneath, so the page content scrolls up to uncover it. |
| Page-transition curtain | client navigation only | Full-screen canvas of digit glyphs (12×17px cells) covers and reveals. **Not reproduced** (single page, no route transitions). |
| Reduced motion | `prefers-reduced-motion` | Marquees stop, cursors stop blinking, WebGL scenes render a still frame, odometer transitions are disabled (motion-safe), and reveals show the final state. |

## Header nav pill (fixed, z-4)
- **Desktop (lg ≥1024):** the pill is centred at top 16px. Its frame is `rounded-8 p-8 bg-black-deep`, with a dithered checker `repeating-conic-gradient(rgba(255,255,255,.22) 0% 25%, transparent 0% 50%) / 4px 4px`, `shadow-lg`, and `ring ring-black-deep`.
  - The inner black panel holds the logo mark (size-30) and the nav links FEATURES · THE REPO · SHOWCASE · PRICING• · FAQ · BLOG, all in mono caption-10 uppercase.
  - Below the links is a light-grey marquee strip reading "NOW AVAILABLE WITH ASTRO".
  - **Scroll-spy:** the link for the section currently in view gets a raised dark tab (`bg-black` pill with a subtle ring). This is the active state visible in the screenshots.
  - PRICING carries an orange pulse dot.
- **Mobile (<lg):** the pill sits top-left at 8px and reads "[logo] Menu [+]".
  - The `+` button (`aria-label="Open menu"`, `aria-expanded`) expands a vertical list of the same links, and the marquee strip stays at the bottom.
  - The `+` icon becomes `—` when open.
  - Screenshots: `20-mobile-hero-390.jpeg`, `21-mobile-menu-open-390.jpeg`.

## Hero
- **Grid:** `grid-rows-[auto_80vh]` on mobile, and 12 columns on lg.
  - The text column is lg `col-span-5`, `pl-80`, vertically centred.
  - The spiral panel is lg `col-span-6 col-start-7`, full height, `bg-black`.
- **Text:** the mono eyebrow is caption-20. The H1 is `text-headline-20 font-medium` (43px at 1440). Body is body-20 `text-dark-grey`. The CTA is the split button [GET]=[ACCESS] (dark) with a pulse dot and links to `/#pricing`.
- **Status grid** (lg only, bottom of the text column): 2 rows typed with the typewriter, `justify-between`. It ends with a blinking block cursor after "DRIFT: 0".
- **SpiralScene** (WebGL2, INTERACTION MODEL: pointer + time):
  - 30 counter-rotating rings of "THE CONTENT ARCHITECTURE." glyphs. The "." renders as a dot.
  - **Hover:** a bell-shaped region under the cursor dissolves letters into dots.
  - **Hold:** press-and-hold charges for 0.9s. The rings freeze, gather inward by up to 12%, shiver and glitch.
  - **Release:** releasing after full charge fires an outward ripple (1.8s) that swells the rings.
  - **Cursor label:** a white mono label follows the cursor, offset 20px, reading "Click & hold" → "Keep holding" → "Release" ("Tap & hold" on touch).
  - **Entrance:** an entrance ripple plays on load.
  - **Scroll:** Lenis scroll velocity adds spin to the rings.
- **Scroll cue** (lg): a `bg-black-deep` 22×68 button at bottom 40px, centred on the column gutter, with a 6px white block stepping down a dotted track (`animate-hero-scroll-cue`, 1.4s steps(7)). Clicking it scrolls one viewport height (Lenis, 1.2s).

## Problems ("textTerminalSection", off-white)
- **Left:** a DitherFrame window titled "COMMON PROBLEMS" (draggable by its title bar; a dashed outline marks the origin). It lists 11 numbered lines, typed sequentially. Each line's hours value fades in (opacity 200ms) once that line is typed. A final summary line types "ESTIMATED TIME LOST: ~24 HOURS PER PROJECT  (3 FULL DAYS)". The body scrolls horizontally (`overflow-x-auto`).
- **Right:** H2 in headline-10 plus two paragraphs in body-20 dark-grey.

## Features ("benefitsSection", #features)
- **GlyphField** (WebGL2) is the sticky full-viewport background (`lg:sticky lg:top-0 lg:h-svh`), overlaid with `bg-black-deep/30`.
  - The phrase tiles the whole grid.
  - The "orb" brightness model sits on the right (lg, max width 55%) or the bottom (mobile).
  - The field is interactive: a hover bell dissolves glyphs, and a click fires a ripple that scrambles glyphs as it passes.
  - It has an entrance ripple and ambient twinkle inside the model.
- **Foreground:** the lg `col-span-5` column has the H2 (headline-10, white) and intro (body-20 ghost-grey). Below are 8 numbered benefits ("001 / AGENT-NATIVE" in mono uppercase, then body-20). They zigzag across three indent columns (x ≈ 80 / 183 / 287px at 1440) as you scroll.

## The repo (#the-repo, h-svh, off-white)
- A full IDE inside a DitherFrame.
  - **Header:** NEXT.JS | ASTRO edition tabs on the left, "THIS IS THE ACTUAL REPO." centred, and on the right a terminal toggle `Ctrl J` and search `Ctrl K`.
  - **Left:** the file tree. Folders expand and collapse with a rotating chevron; files open in the editor.
  - **Centre:** the editor, with a tab bar ("README.MD"), line numbers, a syntax-highlighted overlay under an **editable** transparent textarea, and a code minimap on the right.
  - **Bottom:** the TERMINAL, an interactive fake shell.
  - **Footer:** `⎇ MAIN · UPDATED TODAY` on the left and `▮ 162 COMMITS` on the right (112 for Astro).
- **Terminal commands:** `help, ls, cd, tree, cat, open, grep, plop, history, pwd, whoami, echo, clear, git`. Tab completes paths and up/down recalls history. Real outputs are in `source/terminal-session-2.txt`:
  - `git` prints `main · Updated today · 162 commits` and an ASCII commit-volume chart.
  - `plop` prompts for a name, prints generator ✔ lines, and adds the files to the tree.
  - The first line is pre-filled: `~/the-content-architecture-next-js > get-access   # €399 · was €549 · one-time`.
- The edition tab switches the tree, README, cwd (`~/the-content-architecture-astro`) and commit count. Data for both is in `source/ide-data.json`.

## Showcase (#showcase, black)
- **Backdrop:** a GlyphField (background-only, non-interactive, 30fps, no entrance), with phrase `glyph-phrases.json → showcase`.
- **Header:** H2 headline-10 "The work that gets remembered." plus body-20 with dotted-underline links (Awwwards, FWA, CSSDA).
- **Grid:** 2 columns on lg of 16:9 cards. Each card is an **AsciiImage** (120×37, 64 levels, reveal on hover) with the real screenshot `<img>` stacked on top at `opacity-0` → `group-hover:opacity-100` (500ms ease-out). Below each card is its mono uppercase label. There are 11 cards.
- Mobile: 1 column. On touch devices (`pointer: coarse`), every card has `data-active=true`, so all screenshots are visible. *(Verified 2026-09-12.)*

## Reviews (#reviews, black)
- Uses the same GlyphField backdrop as Showcase, with phrase `reviews`.
- **Carousel:** a horizontal scroll-snap row of tall DitherFrame cards, each showing a large quote (headline-10 white).
  - The quote types in with a trailing bar cursor when its card becomes active.
  - The footer row has an ASCII avatar (32×18 grid, round, 48px), a name (mono caption-10 white) and a role (white/40).
- **Controls:** `[<]  01 / 03  [>]` in mono, centred under the row.

## Pricing (#pricing, off-white)
- **Header:** H2 on 3 lines ("Two editions. / One architecture. / Lifetime updates.") on the left. On the right, 5 overlapping 32px GitHub avatars and "TRUSTED BY 40+ ENGINEERS".
- **Edition cards:** 2 columns (NEXT.JS, ASTRO). Each card is 3 stacked `bg-black rounded-8` blocks joined by vertical connectors at both edges:
  - price block: tag, "● AVAILABLE NOW" pill, then `€399` plus a struck-through `€549`
  - two numbered spec lines
  - a light split button [GET]=[ACCESS]
  - The price digits roll from 0 to their value (≈1s ease-out) when they enter the viewport. *(Verified 2026-09-12.)*
- **Includes panel:** a full-width black block titled "EVERY EDITION INCLUDES", listing numbered items in 2 CSS columns on lg.

## FAQ (#faq, black)
- Uses the GlyphField backdrop with phrase `faq`.
- **Layout:** H2 "Before you buy" on the left (lg col-span-5). A sticky light [GET]=[ACCESS] button sits at the bottom-left of the column.
- **Accordion** on the right: rows read `Q.001 / QUESTION` (the number in white/40), and each has a 20px square `+`/`−` toggle. Q.001 is open by default.
  - Answers are body-20 white.
  - Rows are divided by `border-white/10`.
  - A single item is open at a time. There are 17 items; height and opacity transition over ≈350ms; the `+` bar rotates 90°. *(Verified 2026-09-12.)*

## Banner (off-white)
- A DitherFrame titled "THE CONTENT ARCHITECTURE" containing a `<pre>` figlet (`/$$` font) of "The next 3 days / are yours." in white mono.

## Footer (sticky reveal, black)
- **Left:** an email input (`h-48 rounded-8 border border-current/20 px-16 font-mono`, placeholder "your@email.com"), then a light split button [STAY]=[UPDATED].
- **Right:** a right-aligned mono uppercase link list: BLOG, ROADMAP, GET ACCESS•, PRIVACY POLICY, TERMS OF SERVICE, IMPRINT. Links use the odometer.
- **Bottom:** a divider, then "© 2026 THE CONTENT ARCHITECTURE" / "BUILT BY EDOARDOLUNARDI.DEV".
- A faint phrase-field backdrop sits behind.

## Fixed overlays
- **Minimap** (top-right, `z-3`, 16:9, h-44 / lg h-54):
  - A live thumbnail of the page (a 96px-wide canvas strip that translates with scroll).
  - An orange scan line sweeps down every 5s (`minimapScan` / `minimapScanCounter`).
  - Hover shows an accent ring and an "Inspect ↗" tooltip.
  - Its click opens Studio mode on the original; **our clone renders it non-interactive**.
- **"Learn more" widget** (bottom-right, z-4): a [LEARN MORE] label, a horizontal connector, and a 48px `+` square, all ghost-grey.
  - Clicking opens the **README drawer**: a right-side dialog (`lg:max-w-960`, mid-grey) over a dimmed backdrop.
  - The drawer holds a sticky TOC ("001 / WHY THIS EXISTS", "002 / WHY I KEEP SHIPPING IT", "003 / WHO AM I") with odometer hover, scrollable essay content, and an X / CLOSE button.
  - Esc or clicking the backdrop closes it.

## Recon addendum (2026-09-12)
- **Complete IDE data:** the RSC payload holds both editions' full trees (every file's one-line content), repo stats (branch, "Updated today", commits, and 52 weekly commit counts) and the CTA. See `source/ide-rsc.json`, merged with the README texts into `src/components/…/root-8a5edab2/data/ide.json`.
- **IDE editor:**
  - A transparent editable textarea over a highlighted `<pre>`, with a line gutter and a code minimap. Rows are `min(4, avail/lines)` tall; bars are 0.5px per char, capped at 52px.
  - The highlight palette:
    - md heading `#9fb6d6`
    - list marker `white/35`
    - inline code `#d6a878`
    - bold `white/90`
    - links `white/75`
    - fences `white/40`
    - code comments `white/30 italic`
- **IDE search palette** (Ctrl K): an overlay inside the IDE window listing every file with its path. Ranking is prefix, then includes, then path. Arrows, Enter and Esc work.
- **IDE terminal toggle** (Ctrl J): hides the terminal pane and its resizers. The footer "162 COMMITS" button shows the terminal and runs `git`.
- **Resizable panes:**
  - the explorer width (240px, max 60%)
  - the terminal height (200px, max 70%)
  - a corner handle for both
- **Terminal:** full command set verified (see `source/terminal-commands.json` and `RepoTerminal.spec.md`).
  - `plop` scaffolds a section file and opens it.
  - `sudo rm -rf /` + `y` plays a ~7s timed "deletion" log, then shows a full-screen AMIBIOS overlay; any key reloads (`40-crash-screen-1440.jpeg`).
- **Newsletter popup "Not buying today? Stay close."** (FloatingCapture):
  - appears after 12s, once per session (cookie `tca-prompt-site`), bottom-left, z-50
  - enters with opacity + 24px rise over 0.5s
  - Esc or X closes it
  - it uses the same EmailCapture as the footer: error "Enter a valid email address." (#dc2626), success "You're on the list."
- **Buttons:** every CA pill button has hover colours. Light pills go to white; dark pills go to black-deep. The condensed DOM files had dropped these, so they are now baked into `CaButton`.

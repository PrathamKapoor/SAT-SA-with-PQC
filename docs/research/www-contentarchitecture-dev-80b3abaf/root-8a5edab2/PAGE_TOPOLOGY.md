# contentarchitecture.dev — Page topology

Document height is 13,226px at 1440×900. The only layout breakpoint is `lg` (64rem = 1024px); 768px renders the mobile layout.

```
body (off-white, flex-col)
└─ div.flex.min-h-svh.flex-col
   ├─ header  fixed inset-x-0 top-0 z-4           → SiteNav (pill; pointer-events only on the pill)
   ├─ main    relative z-1 flex-1 flex-col bg-black [&>*:first-child]:flex-1
   │   ├─ 01 Hero            0–900      off-white | SpiralScene panel (black)       pointer/time
   │   ├─ 02 Problems      900–1567     off-white                                   typewriter (viewport)
   │   ├─ 03 Features     1567–4345     black; GlyphField sticky h-svh backdrop     scroll + pointer
   │   ├─ 04 The repo     4345–5245     off-white h-svh; IDE                        click/keyboard
   │   ├─ 05 Showcase     5245–8403     black; GlyphField backdrop; ASCII cards     hover
   │   ├─ 06 Reviews      8403–9355     black; GlyphField backdrop; carousel        click/drag + time
   │   ├─ 07 Pricing      9355–10552    off-white                                   static + hover
   │   ├─ 08 FAQ         10552–12224    black; GlyphField backdrop; accordion       click
   │   ├─ 09 Banner      12224–12781    off-white; framed figlet                    static
   │   ├─ Minimap        fixed top-8 right-8 z-3 (lg top-16 right-16)               time (scan)
   │   ├─ LearnMore      fixed right-8 bottom-8 z-4 (lg right/bottom-16) → README drawer (dialog)
   │   └─ FloatingCapture fixed bottom-left z-50, newsletter popup after 12s (once per session)            time
   └─ footer  sticky bottom-0 z-0 bg-black px-16 py-72 lg:p-80 → SiteFooter (revealed as main ends)
```

Z-layers: footer 0 < main 1 < minimap 3 < header/learn-more 4 < drawer backdrop and dialog (portal, top).

## Component plan (content-driven; the SAT-SA page at `/` reuses every component with its own content)
Namespace: `src/components/sites/www-contentarchitecture-dev-80b3abaf/`

| # | Component (root-8a5edab2/) | CA content file (root-8a5edab2/content/) | Builder |
|---|---|---|---|
| — | shared/GlyphField.tsx (replaces stub) | — | B1 |
| — | shared/SpiralScene.tsx (replaces stub) | — | B2 |
| 00 | SiteNav.tsx | nav.ts | B3 |
| 01 | HeroSection.tsx | hero.ts | B4 |
| 02 | ProblemsSection.tsx | problems.ts | B5 |
| 03 | FeaturesSection.tsx | features.ts | B6 |
| 04 | RepoSection.tsx + repo/RepoSearch.tsx | repo.ts (data/ide.json) | B7d |
| 04a | repo/RepoFileTree.tsx | — | B7a |
| 04b | repo/RepoEditor.tsx + repo/highlight.tsx | — | B7b |
| 04c | repo/RepoTerminal.tsx + terminal-engine.ts + CrashScreen.tsx | — | B7c |
| 05 | ShowcaseSection.tsx | showcase.ts | B8 |
| 06 | ReviewsSection.tsx | reviews.ts | B9 |
| 07 | PricingSection.tsx | pricing.ts | B10 |
| 08 | FaqSection.tsx | faq.ts | B11 |
| 09/13 | BannerSection.tsx + SiteFooter.tsx | banner.ts, footer.ts | B12 |
| 10–12 | Minimap.tsx + LearnMore.tsx (+ ReadmeDrawer) + FloatingCapture.tsx | learn-more.ts, floating-capture.ts | B13 |

Every section component exports `XxxContent` (its props contract) and `XxxSection({ content })`. The shared primitives in `shared/` were built by the foreman during the foundation phase: Odometer, CaButton, EmailCapture, Connector, PulseDot, DitherFrame, Marquee, Reveal, AsciiImage, DeferredMount, PageShell, SmoothScroll, hooks, icons, and glyph-model.

Assembly (foreman): `src/app/reference/contentarchitecture/page.tsx` renders `PageShell` with header = SiteNav, children = sections 01–09, overlays = Minimap + LearnMore, and footer = SiteFooter.

Repo parts share `root-8a5edab2/repo/model.ts` (types + path helpers, foreman-owned); the three sub-components start as stubs with final props so B7a–d build in parallel.

Easter egg: `sudo rm -rf /` → `y` in the IDE terminal ends in a full-screen BIOS overlay (`z-10000`, portal) — any key reloads the page.

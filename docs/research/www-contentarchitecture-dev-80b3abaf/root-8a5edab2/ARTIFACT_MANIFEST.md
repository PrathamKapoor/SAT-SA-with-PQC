# Artifact manifest — contentarchitecture.dev (root)

| Artifact | Local path | Source | Notes |
|---|---|---|---|
| Showcase screenshots ×11 | `public/sites/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/images/showcase-*.jpg\|png` | cdn.sanity.io (earlier draft session) | Hover-reveal images over the ASCII cards |
| Testimonial avatars ×3 | `…/root-8a5edab2/avatars/{julian-fella,elliott-mangham,malik-kotb}.png` | cdn.sanity.io (earlier draft session) | |
| Maintainer portrait | `…/root-8a5edab2/avatars/maintainer.jpg` | cdn.sanity.io `db451abc…-1566x1566.jpg` | README drawer "003 / WHO AM I" |
| Trusted-by avatars ×5 | `…/root-8a5edab2/avatars/trusted-*.png` | github.com/{user}.png | Pricing header |
| Favicons (light/dark) | `public/sites/www-contentarchitecture-dev-80b3abaf/shared/seo/icon-{light,dark}.png` | cdn.sanity.io | `/favicon.ico` on origin → HTTP 500 (not recoverable; PNG icons used) |
| OG image | `…/shared/seo/og-image.png` | cdn.sanity.io `fa6b9eea…-1920x1008.png` | |
| ASCII grids ×14 | `src/components/sites/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/data/ascii-grids.json` | RSC payload `cells` text chunks (exact) | 11 showcase at 120×37, 3 avatars at 32×18; 64 levels; level = charCode−33 |
| Orb brightness model | `…/root-8a5edab2/data/orb-model.json` | JS module 259878 / RSC `cellBrightness` (exact) | 160×88 bytes, base64; CA artwork — reference route only |
| Glyph phrases + atlas | `…/root-8a5edab2/data/glyph-phrases.json` | RSC + BenefitsSectionBackground chunk | features / showcase / reviews / faq |
| Logo mark + IDE icons | `…/shared/icons.tsx` | inline SVG in DOM (exact paths) | |
| IDE data (both editions) | `docs/research/…/source/ide-data.json` | live DOM (tree rows with depth, README textarea values) | depth = (padding − 20) / 28; `expanded` non-null = folder |
| Terminal outputs | `docs/research/…/source/terminal-session-2.txt` | typed into the live terminal | help, git, ls, plop |
| Compiled CSS | `docs/research/…/source/site.css` | `/_next/static/immutable/chunks/1-ywrl4d8ogb9.css` | tokens replicated in `src/app/globals.css` |
| Condensed DOM per section | `docs/research/…/dom/*.html` | live DOM at 1440 after full scroll | odometer stacks collapsed to `<Odometer text>`; svgs → `<Icon id>` (see `source/svgs.json`) |

No Atlas Cloud generated fallbacks were used.

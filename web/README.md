# SAT-SA web UI (`web/`)

The public SAT-SA frontend: a landing page and a supervisory **workbench**,
built with Next.js 16 / React 19 / Tailwind 4.

- **Live:** https://sat-sa-with-pqc-81gi.onrender.com/
- **Deployed by:** `../render.yaml`. Render still builds the separate
  `feat/sat-sa-site` branch, not this folder. This folder holds the same UI
  code as that branch at the time it was moved here. Until Render is pointed at
  `web/` on `main`, keep the two in sync, or the live site will drift from this folder.
- **Origin:** moved from the `feat/sat-sa-site` branch, which was built on the
  MIT-licensed [ai-website-cloner-template](https://github.com/JCodesMore/ai-website-cloner-template)
  (see `LICENSE`).

## What it is and is not

| Route | Content |
|---|---|
| `/` | Landing page. Stats and walkthrough come from `src/components/sites/sat-sa-with-pqc/root/content/*.ts`, captured from a run of the Python demo |
| `/workbench/*` | Overview, entities, findings, review queue, submissions, trends, governance, reports, admin |
| `/reference/contentarchitecture` | Leftover design reference from the template. Some of its shared helpers (`Reveal`, `CaButton`, `SmoothScroll`, `hooks`) are still imported by the SAT-SA pages |

**The workbench does not call the Python backend.** All data is static TypeScript
in `src/components/sites/sat-sa-with-pqc/workbench/data/`, and review actions only
change the viewer's own browser state (React state persisted to `localStorage`,
see `workbench/state/WorkbenchContext.tsx`). The backend
(`../satsa/`) has its own server-rendered UI (`python scripts/serve_ui.py`) and a
small JSON API (`/api/entities`, `/api/entities/{id}/risk`). Connecting the two is
open prototype work.

## Commands

Requires Node >= 24 (see `.nvmrc`).

```bash
cd web
npm ci
npm run dev          # http://localhost:3000
npm run check        # lint + typecheck + production build (what CI runs)
npm run build && npm start

# UI smoke tests against a running server (default http://localhost:3001).
# Known stale: both tests fail against the live site too (they expect
# `data-grainient-mode="light"` and one "Open Review Queue" button, which the
# current UI no longer renders). They are not part of CI until updated.
SAT_SA_BASE_URL=http://localhost:3000 npm run test:ui

# Production container (the same image Render builds)
docker build -t sat-sa-web . && docker run -p 3000:3000 sat-sa-web
```

## Layout

```
src/app/                         routes (/, /workbench/*, /reference/*)
src/components/sites/sat-sa-with-pqc/
  root/                          landing page sections + content/*.ts (static copy + demo numbers)
  workbench/data/                static workbench datasets
  workbench/state/               client-side state (review decisions, filters)
  workbench/ui/                  workbench components
  shared/                        charts, gauges, icons
src/components/reactbits/        visual effects (Grainient, Prism, MaskedHeading)
src/components/sites/www-contentarchitecture-dev-80b3abaf/   template reference + shared helpers
public/                          static assets
docs/design-references/satsa-with-pqc/   screenshots of the Python UI used as design input
tests/                           node:test smoke tests (need a running server)
```

# SAT-SA web UI (`web/`)

The SAT-SA product interface: a public site and the secure supervisory
application. Next.js 16, React 19, Tailwind CSS 4, Lucide icons.

- **Live:** https://sat-sa-with-pqc-81gi.onrender.com/ (Render builds the
  `feat/sat-sa-site` branch, see `../render.yaml`; this folder is the current
  UI and will replace that branch once hosting is pointed here)
- **Backend contract:** [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md)

## Surfaces

| Surface | Routes | Data |
|---|---|---|
| Public site | `/`, `/methodology`, `/security` | Product description only. No entity, finding or evidence data. |
| Sign in | `/login` | Issued credential (backend adapter) or a development identity (development adapter) |
| Application | `/workbench/*` | Through `SatsaDataSource`; requires a session |

Application routes, grouped as in the sidebar:

- **Command:** Workbench (fits the viewport, no page scroll on desktop), Overview
- **Supervision:** Entities, entity detail, Findings, finding detail (investigation workspace), Review queue, Decisions
- **Analytics:** Analytics, Benchmarks, Pipeline
- **Data:** Submissions, Ingest, Security data
- **Intelligence:** Agents, Architecture, Reports (printable per entity)
- **Trust:** TRUST-SAT, Audit
- **Admin:** Administration, System

Navigation is filtered by role (viewer, analyst, supervisor, auditor,
administrator), mirroring `qsmlops/security/permissions/model.py`. The backend
remains the only place a permission is enforced.

## Sessions: backend or development

`SATSA_AUTH_ADAPTER` selects how a session is established (`src/lib/auth/config.ts`):

| Value | Used when | Behaviour |
|---|---|---|
| `development` | default under `npm run dev` | Sign-in lists five development identities (`dev-admin`, `dev-supervisor`, `dev-analyst`, `dev-auditor`, `dev-viewer`). One click enters the application. The session is a browser-session cookie; the top bar shows "Development session" and an exit action. |
| `backend` | default for every production build (`next build`, Docker, Render) | Sign-in takes a credential issued by the SAT-SA backend (`POST /api/v1/session`). |

Development identities exist only in this frontend. They carry no credential,
are validated against a fixed list on every request, and are never sent to a
backend API. A production build only offers them if `SATSA_AUTH_ADAPTER=development`
is set explicitly. Roles and permissions are the backend's
(`qsmlops/security/permissions/model.py`), mirrored in `src/lib/auth/permissions.ts`.

## Data: real, fixture, empty

`SATSA_DATA_SOURCE` selects the adapter (read on the server only):

- `fixture` (default): `src/lib/mocks/fixture.json`, **generated** from a real
  backend run over the committed synthetic demo dataset by
  `scripts/export-demo-fixture.py`. It is never hand-edited and contains no
  review decisions, because the demo records none.
- `api`: the SAT-SA backend at `SATSA_API_BASE_URL`, per `docs/API_CONTRACT.md`.

The top bar always shows the origin. In fixture mode, a supervisor's
decisions are kept in the browser only and are labelled "development session"
wherever they appear. Figures quoted from repository reports live in
`src/content/documented.ts` with their source path. Where the backend has no
endpoint yet, pages show a labelled empty state instead of placeholder numbers.

## Commands

Requires Node 24 (`.nvmrc`).

```bash
cd web
npm ci
npm run dev                  # http://localhost:3000: fixture data, development sessions
npm run check                # lint + typecheck + production build (CI runs this)
SAT_SA_BASE_URL=http://localhost:3000 npm run test:ui   # smoke tests against a running server

# regenerate the fixture (from the repository root, backend installed)
python web/scripts/export-demo-fixture.py

# against the backend once the API contract is implemented
SATSA_DATA_SOURCE=api SATSA_API_BASE_URL=http://127.0.0.1:8000 npm run dev

docker build -t sat-sa-web . && docker run -p 3000:3000 sat-sa-web
```

## Layout

```
src/app/(public)/            public site (product, methodology, security)
src/app/login/               sign-in (credential form or development identities)
src/app/workbench/           secure application, one folder per route
src/components/ui/           design-system primitives (button, badges, data, dialog, layout, states, tooltip)
src/components/shell/        app shell: sidebar, top bar, navigation icons
src/components/domain/       SAT-SA components (finding row, evidence lifecycle, review panel, provenance chain, ...)
src/components/public/       public chrome and the evidence field (interactive canvas hero)
src/lib/types/domain.ts      domain types mirroring the backend records
src/lib/api/                 SatsaDataSource interface, fixture and HTTP adapters
src/lib/auth/                session provider, backend and development adapters, identities, roles
src/lib/domain/              labels, formatting, lifecycle and measure derivations
src/lib/model.ts             server-side view models (joins only, no invented scores)
src/lib/mocks/               development fixture (generated) and its adapter
src/content/documented.ts    figures transcribed from repository reports, with source
docs/API_CONTRACT.md         endpoints the backend implements for api mode
scripts/export-demo-fixture.py  fixture generator (reads the backend, writes nothing to it)
```

## Design tokens

Defined in `src/app/globals.css`: white and near-white surfaces, navy ink,
purple as the SAT-SA identity and trust colour, blue for analytical context,
orange for attention, red only for critical or failed states. State is never
shown by colour alone. Motion respects `prefers-reduced-motion`.

The MIT `LICENSE` in this folder is from the Next.js starter the UI was
originally scaffolded from.

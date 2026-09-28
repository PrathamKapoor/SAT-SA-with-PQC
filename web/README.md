# SAT-SA web UI (`web/`)

The SAT-SA product interface: a public site and the supervisory workbench.
Next.js 16, React 19, Tailwind CSS 4, Lucide icons.

The workbench is a client of the SAT-SA API (`../docs/API_CONTRACT.md`). Every
entity, finding, score, recommendation, decision and trust state it shows is
read from the backend; the UI never computes an analytical value and has no
fixture or mock data path.

- **Hosting:** no hosting provider is currently configured. The production
  image is `web/Dockerfile` (standalone Next.js server on `PORT`, default
  3000); see `../docs/deployment.md` for the provider-neutral hosting contract.
- **Integration guide:** `../docs/FRONTEND_API_HANDOFF.md`.

## Surfaces

| Surface | Routes | Data |
|---|---|---|
| Public site | `/`, `/methodology`, `/security` | Product description only. No entity, finding or evidence data. |
| Sign in | `/login` | Credential issued by a SAT-SA administrator |
| Organization | `/organization` | The signed-in user's memberships (`GET /api/v1/organizations`) |
| Workbench | `/workbench/*` | The SAT-SA API, scoped to the selected organization |

Workbench routes, grouped as in the sidebar:

- **Command:** Workbench
- **Supervision:** Entities, entity detail, Findings, finding detail (investigation workspace), Review queue, Decisions
- **Analytics:** Analytics, Benchmarks, Analysis runs, run detail (progress, findings, risk, recommendations, decision, TRUST-SAT)
- **Data:** Submissions, Ingest, Security data
- **Intelligence:** Agents, Architecture, Reports (printable per entity)
- **Trust:** TRUST-SAT, Audit
- **Admin:** Members, System

Navigation is filtered by the user's role in the selected organization,
mirroring `qsmlops/security/permissions/model.py`. The backend is the only place
a permission is enforced; a refused call is shown as "Not permitted" with the
backend's request ID.

## How the integration works

- **Server-side only.** Pages are server components and writes are server
  actions (`src/lib/workbench/actions.ts`). They call the API through
  `src/lib/api/client.ts`; the browser never receives a token and never calls
  the API, so no CORS configuration is needed.
- **Sessions.** Sign-in posts the credential once to `POST /api/v1/session` and
  stores only the returned session token in the HttpOnly `satsa_session`
  cookie. Requests send it as `Authorization: Bearer`. Sign-out revokes that
  session with `DELETE /api/v1/session`. An expired or revoked session sends the
  user back to sign-in (`/logout?reason=expired` clears the cookies).
- **Organization.** `GET /api/v1/organizations` lists memberships. With one
  membership it is selected automatically; with several, `/organization` asks.
  The selection is kept in the HttpOnly `satsa_org` cookie and sent as
  `X-Organization-ID`; the backend re-checks membership on every call.
- **Pagination.** Lists page through `{items, limit, offset, has_more}` with
  previous/next links (`src/components/ui/pager.tsx`); aggregates read every
  page up to a stated bound.
- **Errors.** Every backend error envelope is shown with its title, a retry
  action where retrying can help, and the request ID
  (`src/components/ui/api-state.tsx`). Stack traces and internals never reach
  the page.
- **Live state.** Pages with work in progress (queued or running runs, a run
  being finalized after its decision) re-read the server every few seconds;
  nothing animates progress the backend has not reported.

## Local development (offline, no Docker)

Requires Python with the repository installed (`pip install -e .` at the root)
and Node 24 (`.nvmrc`).

```bash
# 1. Backend: API + separate worker on SQLite, from the repository root.
#    First start bootstraps an organization with an administrator, an analyst
#    and a supervisor; their credentials are written to .satsa-local/credentials.json.
python scripts/local_stack.py --seed-demo        # --seed-demo loads the five-CSE demo through the API

# 2. Web UI, in another terminal.
cd web
npm ci
SATSA_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

The demo is real backend output: `scripts/seed_demo_via_api.py` uploads the
committed CSVs in `docs/demo/submissions/`, validates them and starts runs; the
worker computes everything. Sign in with a credential from
`.satsa-local/credentials.json` (local development only).

## Checks

```bash
npm run check                # lint + typecheck + production build (CI)
npm run build && npm run test:e2e
                             # browser workflow against a real backend (CI job web-e2e):
                             # starts API + worker on a throwaway SQLite database
SAT_SA_BASE_URL=http://localhost:3000 npm run test:ui   # smoke tests against a running server
```

The end-to-end test (`e2e/workbench.spec.ts`) signs in as an analyst, ingests
the six files of a demo CSE through the Ingest page, waits for validation and
for the worker to release the run, opens a finding and its evidence records,
checks the priority ranking, then signs in as a supervisor, records the
decision, waits for TRUST-SAT finalization and verifies it, and reads the audit
trail. Set `PLAYWRIGHT_CHANNEL=msedge` (or `chrome`) to use an installed
browser, or run `npx playwright install chromium` once.

## Layout

```
src/app/(public)/            public site (product, methodology, security)
src/app/login/               credential sign-in
src/app/organization/        organization selection
src/app/logout/              clears an invalid session
src/app/workbench/           workbench, one folder per route
src/components/ui/           design-system primitives, API error state, pager
src/components/shell/        app shell: sidebar, top bar, navigation icons
src/components/domain/       SAT-SA components (finding list, run controls, ingest workflow, members admin, ...)
src/components/public/       public chrome and the evidence field (interactive canvas hero)
src/lib/api/                 wire types, server-side client, session/organization context, error model
src/lib/workbench/           server actions and shared read joins
src/lib/auth/                sign-in/out actions and the role map
src/lib/domain/              labels, formatting, status vocabularies, ingest pre-check
src/content/documented.ts    figures transcribed from repository reports, with source
e2e/                         Playwright end-to-end test and its backend setup
```

## Design tokens

Defined in `src/app/globals.css`: white and near-white surfaces, navy ink,
purple as the SAT-SA identity and trust colour, blue for analytical context,
orange for attention, red only for critical or failed states. State is never
shown by colour alone. Motion respects `prefers-reduced-motion`.

The MIT `LICENSE` in this folder is from the Next.js starter the UI was
originally scaffolded from.

# SAT-SA web UI: backend API contract

The web workbench uses the backend's contract, not a contract of its own:

- **Contract:** [`../../docs/API_CONTRACT.md`](../../docs/API_CONTRACT.md) (46 routes,
  kept in step with the live application by `tests/test_phase17_api_contract.py`).
- **How the workbench uses it:** [`../../docs/FRONTEND_API_HANDOFF.md`](../../docs/FRONTEND_API_HANDOFF.md).
- **Wire types in this app:** `src/lib/api/types.ts`; client: `src/lib/api/client.ts`.

An earlier version of this file proposed a different, frontend-shaped API
(global unpaginated arrays in camelCase, per-finding reviews, about fifteen
routes the backend does not serve). That proposal was retired in Phase 18 when
the workbench was rewired to the real API; it is in the git history.

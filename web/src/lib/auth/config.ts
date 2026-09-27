import "server-only";

/**
 * Which session adapter the application uses. Read on the server only.
 *
 *   SATSA_AUTH_ADAPTER=backend      Credentials issued by the SAT-SA backend (production).
 *   SATSA_AUTH_ADAPTER=development  Frontend-only development identities for local preview.
 *
 * When unset, `next dev` uses the development adapter and every production
 * build (`next build` / `next start`, Docker) uses the backend adapter.
 * A production deployment only gets development sessions if someone sets
 * SATSA_AUTH_ADAPTER=development explicitly, and the UI then labels every page.
 */
export type AuthAdapterKind = "development" | "backend";

export function authAdapterKind(): AuthAdapterKind {
  const configured = process.env.SATSA_AUTH_ADAPTER;
  if (configured === "development" || configured === "backend") return configured;
  return process.env.NODE_ENV === "production" ? "backend" : "development";
}

export function backendAuthConfigured(): boolean {
  return Boolean(process.env.SATSA_API_BASE_URL);
}

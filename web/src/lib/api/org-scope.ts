import "server-only";

import { cache } from "react";

/**
 * The organization the current request is scoped to, as resolved by
 * requireContext (a validated stored selection, or the user's only
 * membership). Request-scoped; the API client sends it as X-Organization-ID.
 */
export const requestOrganization = cache((): { id: string | null } => ({ id: null }));

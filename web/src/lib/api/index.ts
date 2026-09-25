import "server-only";

import { fixtureSource } from "@/lib/mocks/fixture-source";
import { createHttpSource } from "./http";
import type { SatsaDataSource } from "./source";

export type { DataOrigin, FindingQuery, SatsaDataSource } from "./source";

/**
 * Select the data source from the environment (read on the server only):
 *
 *   SATSA_DATA_SOURCE=fixture  (default) development fixture, clearly labelled in the UI
 *   SATSA_DATA_SOURCE=api      SAT-SA backend at SATSA_API_BASE_URL
 */
export function getSource(): SatsaDataSource {
  if (process.env.SATSA_DATA_SOURCE === "api") {
    const base = process.env.SATSA_API_BASE_URL;
    if (!base) throw new Error("SATSA_DATA_SOURCE=api requires SATSA_API_BASE_URL");
    return createHttpSource(base);
  }
  return fixtureSource;
}

export function isFixtureMode(): boolean {
  return process.env.SATSA_DATA_SOURCE !== "api";
}

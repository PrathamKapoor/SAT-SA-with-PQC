"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { BackendReviewAction } from "@/lib/types/domain";

/**
 * DEVELOPMENT-SESSION decisions (fixture mode only).
 *
 * With no backend connected there is nowhere authoritative to record a
 * review decision, so decisions made while exploring the UI are kept in
 * this browser's localStorage, shown with a "development session" label,
 * and never presented as backend records. In api mode this store is unused:
 * decisions go to POST /api/v1/findings/{id}/reviews.
 */
export interface DevDecision {
  id: string;
  findingId: string;
  action: BackendReviewAction;
  reason: string;
  occurredAt: number;
  role: string;
  findingContentDigest: string;
}

interface Store {
  decisions: DevDecision[];
  record: (d: Omit<DevDecision, "id" | "occurredAt">) => DevDecision;
  clear: () => void;
  latestFor: (findingId: string) => DevDecision | undefined;
}

const KEY = "satsa.dev-decisions.v1";
const Ctx = createContext<Store | null>(null);

export function ReviewStoreProvider({ children }: { children: ReactNode }) {
  const [decisions, setDecisions] = useState<DevDecision[]>([]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(KEY);
      // eslint-disable-next-line react-hooks/set-state-in-effect -- hydrate from storage once on mount
      if (raw) setDecisions(JSON.parse(raw) as DevDecision[]);
    } catch {
      /* storage unavailable: start empty */
    }
  }, []);

  const persist = useCallback((next: DevDecision[]) => {
    setDecisions(next);
    try {
      localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      /* ignore */
    }
  }, []);

  const record = useCallback<Store["record"]>(
    (d) => {
      const entry: DevDecision = { ...d, id: `devdec_${crypto.randomUUID().slice(0, 12)}`, occurredAt: Date.now() / 1000 };
      persist([...decisions, entry]);
      return entry;
    },
    [decisions, persist],
  );

  const value = useMemo<Store>(
    () => ({
      decisions,
      record,
      clear: () => persist([]),
      latestFor: (findingId) => [...decisions].reverse().find((x) => x.findingId === findingId),
    }),
    [decisions, record, persist],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useReviewStore(): Store {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useReviewStore must be used inside ReviewStoreProvider");
  return ctx;
}

"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/**
 * Re-reads the page from the server while the backend reports work in
 * progress. The page re-renders from persisted backend state; nothing here
 * animates progress the backend has not reported.
 *
 * Every refresh re-renders the whole page (a run page is about a dozen API
 * reads), and the API limits reads per client address. Runs take minutes, so
 * ten seconds keeps the page current without one open tab using most of that
 * budget.
 */
export function AutoRefresh({ active, seconds = 10, label }: { active: boolean; seconds?: number; label: string }) {
  const router = useRouter();
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => router.refresh(), seconds * 1000);
    return () => clearInterval(timer);
  }, [active, seconds, router]);
  if (!active) return null;
  return (
    <p role="status" aria-live="polite" className="text-[12px] text-muted">
      <span aria-hidden="true" className="mr-1.5 inline-block size-1.5 animate-pulse rounded-full bg-info align-middle" />
      {label} Refreshing every {seconds} seconds.
    </p>
  );
}

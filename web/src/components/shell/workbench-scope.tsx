"use client";

import { CalendarRange, Layers } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

export interface ScopeOption {
  value: string;
  label: string;
}

/**
 * Assessment period and cohort for the Workbench. Both come from the data
 * (assessment periods, entity sectors) and filter the Workbench counts
 * through the URL, so the view is shareable and server-rendered.
 */
export function WorkbenchScope({ periods, cohorts }: { periods: ScopeOption[]; cohorts: ScopeOption[] }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params.toString());
    if (value) next.set(key, value);
    else next.delete(key);
    router.replace(`${pathname}${next.size ? `?${next}` : ""}`);
  };

  const select =
    "h-8 appearance-none rounded-sm border border-line-2 bg-paper pr-7 pl-8 text-[13px] font-medium text-ink hover:border-ink/30 focus:border-brand focus:outline-none bg-[length:10px] bg-[right_0.6rem_center] bg-no-repeat";
  const chevron = {
    backgroundImage:
      "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 6'%3E%3Cpath d='M1 1l4 4 4-4' fill='none' stroke='%23586174' stroke-width='1.5'/%3E%3C/svg%3E\")",
  };

  return (
    <div className="hidden items-center gap-2 md:flex">
      <label className="relative">
        <span className="sr-only">Assessment period</span>
        <CalendarRange className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-brand" aria-hidden="true" />
        <select value={params.get("period") ?? ""} onChange={(e) => set("period", e.target.value)} className={select} style={chevron}>
          {periods.length > 1 && <option value="">All periods</option>}
          {periods.map((p) => (
            <option key={p.value} value={periods.length > 1 ? p.value : ""}>
              {p.label}
            </option>
          ))}
        </select>
      </label>
      <label className="relative">
        <span className="sr-only">Cohort</span>
        <Layers className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-brand" aria-hidden="true" />
        <select value={params.get("cohort") ?? ""} onChange={(e) => set("cohort", e.target.value)} className={`${select} min-w-40`} style={chevron}>
          <option value="">All cohorts</option>
          {cohorts.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

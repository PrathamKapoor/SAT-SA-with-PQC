import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import type { Page } from "@/lib/api/types";
import { cn } from "@/lib/utils";

/**
 * Previous/next navigation for a backend collection ({items, limit, offset,
 * has_more}). The page reads `offset` from the URL; nothing assumes the
 * collection arrived complete.
 */
export function Pager<T>({
  page,
  path,
  params = {},
  param = "offset",
  label,
  className,
}: {
  page: Page<T>;
  path: string;
  params?: Record<string, string | undefined>;
  param?: string;
  label: string;
  className?: string;
}) {
  const href = (offset: number) => {
    const q = new URLSearchParams(Object.entries({ ...params, [param]: offset ? String(offset) : undefined }).filter((e): e is [string, string] => Boolean(e[1])));
    const s = q.toString();
    return s ? `${path}?${s}` : path;
  };
  const first = page.items.length ? page.offset + 1 : 0;
  const last = page.offset + page.items.length;
  const prev = page.offset > 0;
  const link = "inline-flex h-7 items-center gap-1 rounded-sm border border-line-2 bg-paper px-2.5 text-[12.5px] text-ink hover:border-ink/40";
  const off = "inline-flex h-7 items-center gap-1 rounded-sm border border-line px-2.5 text-[12.5px] text-faint";
  if (!prev && !page.has_more) {
    return <p className={cn("mt-3 text-[12px] text-muted", className)}>{page.items.length ? `${page.items.length} shown` : ""}</p>;
  }
  return (
    <nav aria-label={label} className={cn("mt-3 flex items-center justify-between gap-3 text-[12.5px] text-muted", className)}>
      <span className="num">
        {first} to {last}
        {page.has_more ? " of more" : ""}
      </span>
      <span className="flex gap-2">
        {prev ? (
          <Link className={link} href={href(Math.max(0, page.offset - page.limit))} rel="prev">
            <ChevronLeft className="size-3.5" aria-hidden="true" />
            Previous
          </Link>
        ) : (
          <span className={off} aria-disabled="true">
            <ChevronLeft className="size-3.5" aria-hidden="true" />
            Previous
          </span>
        )}
        {page.has_more ? (
          <Link className={link} href={href(page.offset + page.limit)} rel="next">
            Next
            <ChevronRight className="size-3.5" aria-hidden="true" />
          </Link>
        ) : (
          <span className={off} aria-disabled="true">
            Next
            <ChevronRight className="size-3.5" aria-hidden="true" />
          </span>
        )}
      </span>
    </nav>
  );
}

/** Read a non-negative integer offset from search params. */
export function offsetOf(value: string | string[] | undefined): number {
  const n = Number(Array.isArray(value) ? value[0] : value);
  return Number.isInteger(n) && n > 0 && n <= 1_000_000 ? n : 0;
}

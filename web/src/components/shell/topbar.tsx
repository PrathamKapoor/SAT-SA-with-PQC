"use client";

import { CalendarRange, Database, FlaskConical, LogOut } from "lucide-react";
import { usePathname } from "next/navigation";
import { Tooltip } from "@/components/ui/tooltip";
import { signOut } from "@/lib/auth/actions";
import { titleFor } from "@/lib/nav";
import { MobileNav, type SidebarProps } from "./sidebar";

export interface OriginInfo {
  kind: "api" | "fixture";
  label: string;
  detail: string;
}

export interface SessionBadge {
  mode: "development" | "backend";
  roleLabel: string;
  principal: string;
}

export function TopBar({ nav, period, origin, session }: { nav: SidebarProps; period: string | null; origin: OriginInfo; session: SessionBadge }) {
  const pathname = usePathname();
  const title = titleFor(pathname);
  return (
    <header className="no-print flex h-14 shrink-0 items-center gap-3 border-b border-line bg-paper/95 px-4 backdrop-blur-sm md:px-6">
      <MobileNav {...nav} />
      <p className="min-w-0 truncate text-[14px] font-semibold text-ink">{title}</p>

      <div className="ml-auto flex min-w-0 items-center gap-2">
        {session.mode === "development" && (
          <div className="flex items-center overflow-hidden rounded-sm border border-attention/40 bg-attention-tint">
            <span
              className="flex items-center gap-1.5 px-2 py-1 font-mono text-[11px] font-semibold tracking-[0.06em] text-attention-strong uppercase"
              title={`Development principal ${session.principal}. Not an authenticated identity.`}
            >
              <FlaskConical className="size-3.5" aria-hidden="true" />
              <span className="max-md:sr-only">Development session ·</span> {session.roleLabel}
              <span className="font-normal tracking-normal text-attention-strong/80 normal-case max-lg:hidden">{session.principal}</span>
            </span>
            <form action={signOut} className="border-l border-attention/30">
              <button type="submit" className="flex items-center gap-1 px-2 py-1 text-[12px] font-medium text-attention-strong hover:bg-attention/10" title="Exit development session">
                <LogOut className="size-3.5" aria-hidden="true" />
                <span className="max-xl:sr-only">Exit development session</span>
              </button>
            </form>
          </div>
        )}
        {period && (
          <span className="hidden items-center gap-1.5 rounded-sm border border-line px-2 py-1 text-[12.5px] text-ink-2 md:inline-flex">
            <CalendarRange className="size-3.5 text-muted" aria-hidden="true" />
            <span className="sr-only">Assessment period </span>
            {period}
          </span>
        )}
        <Tooltip tip={origin.detail} side="bottom">
          <span
            tabIndex={0}
            className={
              origin.kind === "fixture"
                ? "inline-flex items-center gap-1.5 rounded-sm border border-attention/30 bg-attention-tint px-2 py-1 text-[12px] font-medium text-attention-strong"
                : "inline-flex items-center gap-1.5 rounded-sm border border-line px-2 py-1 text-[12px] text-ink-2"
            }
          >
            {origin.kind === "fixture" ? <FlaskConical className="size-3.5" aria-hidden="true" /> : <Database className="size-3.5" aria-hidden="true" />}
            <span className="max-sm:sr-only">{origin.label}</span>
          </span>
        </Tooltip>
      </div>
    </header>
  );
}

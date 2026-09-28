"use client";

import { Building2, Database, LogOut } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Tooltip } from "@/components/ui/tooltip";
import { signOut } from "@/lib/auth/actions";
import { titleFor } from "@/lib/nav";
import { MobileNav, type SidebarProps } from "./sidebar";

export interface TopBarContext {
  organization: string;
  canSwitch: boolean;
  displayName: string;
  roleLabel: string;
}

export function TopBar({ nav, context }: { nav: SidebarProps; context: TopBarContext }) {
  const pathname = usePathname();
  const initials = context.roleLabel.slice(0, 2).toUpperCase();

  return (
    <header className="no-print flex h-14 shrink-0 items-center gap-3 border-b border-line bg-paper/95 px-4 backdrop-blur-sm md:px-6">
      <MobileNav {...nav} />
      <p className="min-w-0 truncate text-[14px] font-semibold text-ink">{titleFor(pathname)}</p>

      <div className="ml-auto flex min-w-0 items-center gap-2">
        {context.canSwitch ? (
          <Link
            href="/organization"
            className="hidden max-w-[16rem] items-center gap-1.5 sm:inline-flex rounded-sm border border-line px-2 py-1 text-[12.5px] text-ink-2 hover:border-ink/40 hover:text-ink"
            title="Switch organization"
          >
            <Building2 className="size-3.5 shrink-0 text-muted" aria-hidden="true" />
            <span className="sr-only">Organization: </span>
            <span className="truncate">{context.organization}</span>
          </Link>
        ) : (
          <span className="hidden max-w-[16rem] items-center gap-1.5 sm:inline-flex rounded-sm border border-line px-2 py-1 text-[12.5px] text-ink-2">
            <Building2 className="size-3.5 shrink-0 text-muted" aria-hidden="true" />
            <span className="sr-only">Organization: </span>
            <span className="truncate">{context.organization}</span>
          </span>
        )}
        <Tooltip tip="Every value on these pages is read from the SAT-SA service. The browser never calls it directly." side="bottom">
          <span tabIndex={0} className="inline-flex items-center gap-1.5 rounded-sm border border-line px-2 py-1 text-[12px] text-ink-2">
            <Database className="size-3.5" aria-hidden="true" />
            <span className="max-lg:sr-only">Live backend</span>
          </span>
        </Tooltip>

        <div className="flex items-center gap-2">
          <span aria-hidden="true" className="flex size-8 items-center justify-center rounded-full bg-brand font-mono text-[11px] font-semibold text-white">
            {initials}
          </span>
          <span className="hidden leading-tight md:block">
            <span className="block text-[13px] font-medium text-ink">{context.displayName}</span>
            <span className="block text-[11.5px] text-muted">{context.roleLabel}</span>
          </span>
          <form action={signOut}>
            <button type="submit" aria-label="Sign out" title="Sign out" className="rounded-sm p-1.5 text-muted hover:bg-sunken hover:text-ink">
              <LogOut className="size-4" aria-hidden="true" />
            </button>
          </form>
        </div>
      </div>
    </header>
  );
}

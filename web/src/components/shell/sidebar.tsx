"use client";

import { ChevronsLeft, ChevronsRight, LogOut, Menu } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Wordmark, BrandMark } from "@/components/brand";
import { Drawer } from "@/components/ui/dialog";
import { signOut } from "@/lib/auth/actions";
import type { NavGroup } from "@/lib/nav";
import { useReviewStore } from "@/lib/review-store";
import { cn } from "@/lib/utils";
import { NavIcon } from "./nav-icon";

export interface SidebarProps {
  groups: NavGroup[];
  signalFindingIds: string[];
  decidedFindingIds: string[];
  user: { displayName: string; roleLabel: string; principal: string };
  sessionMode: "development" | "backend";
}

const COLLAPSE_KEY = "satsa.sidebar.collapsed";

function useAwaitingCount(signalFindingIds: string[], decidedFindingIds: string[]) {
  const { decisions } = useReviewStore();
  const decided = new Set([...decidedFindingIds, ...decisions.map((d) => d.findingId)]);
  return signalFindingIds.filter((id) => !decided.has(id)).length;
}

function NavList({ groups, collapsed, awaiting, onNavigate }: { groups: NavGroup[]; collapsed: boolean; awaiting: number; onNavigate?: () => void }) {
  const pathname = usePathname();
  const isActive = (href: string) => (href === "/workbench" ? pathname === href : pathname === href || pathname.startsWith(`${href}/`));
  return (
    <nav aria-label="Application" className="flex-1 overflow-y-auto px-2.5 pb-4">
      {groups.map((g) => (
        <div key={g.label} className="mt-4 first:mt-2">
          {collapsed ? (
            <div aria-hidden="true" className="mx-2 mb-2 h-px bg-line" />
          ) : (
            <p className="label mb-1 px-2.5 text-[10px] text-faint">{g.label}</p>
          )}
          <ul className="space-y-px">
            {g.items.map((item) => {
              const active = isActive(item.href);
              const count = item.countKey === "awaitingReview" ? awaiting : undefined;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    title={collapsed ? item.label : undefined}
                    className={cn(
                      "group relative flex h-8 items-center gap-2.5 rounded-sm px-2.5 text-[13.5px] transition-colors",
                      active ? "bg-brand-tint font-medium text-brand-strong" : "text-ink-2 hover:bg-sunken hover:text-ink",
                      collapsed && "justify-center px-0",
                    )}
                  >
                    {active && <span aria-hidden="true" className="absolute inset-y-1.5 -left-2.5 w-[3px] rounded-r-sm bg-brand" />}
                    <NavIcon name={item.icon} className={cn("size-[17px] shrink-0", active ? "text-brand" : "text-muted group-hover:text-ink")} />
                    {collapsed ? (
                      <span className="sr-only">{item.label}</span>
                    ) : (
                      <span className="truncate">{item.label}</span>
                    )}
                    {count != null && count > 0 && (
                      <span
                        className={cn(
                          "num rounded-xs bg-attention-tint px-1.5 text-[11px] font-medium text-attention-strong",
                          collapsed ? "absolute top-0.5 right-0.5 px-1 text-[9.5px]" : "ml-auto",
                        )}
                      >
                        {count}
                        <span className="sr-only"> awaiting review</span>
                      </span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function SessionFooter({ user, sessionMode, collapsed }: Pick<SidebarProps, "user" | "sessionMode"> & { collapsed: boolean }) {
  const initials = user.roleLabel.slice(0, 2).toUpperCase();
  return (
    <div className={cn("border-t border-line p-2.5", collapsed && "flex flex-col items-center gap-2")}>
      <div className={cn("flex items-center gap-2.5", collapsed && "justify-center")}>
        <span aria-hidden="true" className="flex size-8 shrink-0 items-center justify-center rounded-sm bg-ink font-mono text-[11px] font-semibold text-white">
          {initials}
        </span>
        {!collapsed && (
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-medium text-ink">{user.roleLabel}</p>
            <p className="truncate font-mono text-[11px] text-muted">{sessionMode === "development" ? `${user.principal} · development` : user.displayName}</p>
          </div>
        )}
        <form action={signOut}>
          <button type="submit" aria-label={sessionMode === "development" ? "Exit development session" : "Sign out"} title={sessionMode === "development" ? "Exit development session" : "Sign out"} className="rounded-sm p-1.5 text-muted hover:bg-sunken hover:text-ink">
            <LogOut className="size-4" aria-hidden="true" />
          </button>
        </form>
      </div>
    </div>
  );
}

export function Sidebar(props: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const awaiting = useAwaitingCount(props.signalFindingIds, props.decidedFindingIds);

  useEffect(() => {
    try {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- restore persisted preference once
      setCollapsed(localStorage.getItem(COLLAPSE_KEY) === "1");
    } catch {
      /* ignore */
    }
  }, []);

  const toggle = () => {
    setCollapsed((c) => {
      try {
        localStorage.setItem(COLLAPSE_KEY, c ? "0" : "1");
      } catch {
        /* ignore */
      }
      return !c;
    });
  };

  return (
    <aside
      aria-label="Primary"
      className={cn("no-print hidden h-dvh shrink-0 flex-col border-r border-line bg-paper transition-[width] duration-200 lg:flex", collapsed ? "w-[60px]" : "w-[232px]")}
    >
      <div className={cn("flex h-14 items-center border-b border-line", collapsed ? "justify-center" : "justify-between px-4")}>
        <Link
          href="/"
          title="Return to SAT-SA public site"
          className="-mx-1.5 rounded-sm px-1.5 py-1 transition-colors hover:bg-sunken focus-visible:outline-2 focus-visible:outline-brand"
        >
          <span className="sr-only">Return to SAT-SA public site: </span>
          {collapsed ? <BrandMark /> : <Wordmark sub />}
        </Link>
        {!collapsed && (
          <button type="button" onClick={toggle} aria-label="Collapse navigation" title="Collapse navigation" className="rounded-sm p-1 text-faint hover:bg-sunken hover:text-ink">
            <ChevronsLeft className="size-4" aria-hidden="true" />
          </button>
        )}
      </div>
      {collapsed && (
        <button type="button" onClick={toggle} aria-label="Expand navigation" title="Expand navigation" className="mx-auto mt-2 rounded-sm p-1.5 text-faint hover:bg-sunken hover:text-ink">
          <ChevronsRight className="size-4" aria-hidden="true" />
        </button>
      )}
      <NavList groups={props.groups} collapsed={collapsed} awaiting={awaiting} />
      <SessionFooter user={props.user} sessionMode={props.sessionMode} collapsed={collapsed} />
    </aside>
  );
}

/** Below the lg breakpoint the navigation lives in a drawer opened from the top bar. */
export function MobileNav(props: SidebarProps) {
  const [open, setOpen] = useState(false);
  const awaiting = useAwaitingCount(props.signalFindingIds, props.decidedFindingIds);
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open navigation"
        className="-ml-1 rounded-sm p-1.5 text-ink-2 hover:bg-sunken lg:hidden"
      >
        <Menu className="size-5" aria-hidden="true" />
      </button>
      <Drawer open={open} onClose={() => setOpen(false)} title="Navigation" side="left">
        <div className="flex h-full flex-col">
          <div className="flex h-14 items-center border-b border-line px-4">
            <Link href="/" title="Return to SAT-SA public site" className="-mx-1.5 rounded-sm px-1.5 py-1 hover:bg-sunken" onClick={() => setOpen(false)}>
              <span className="sr-only">Return to SAT-SA public site: </span>
              <Wordmark sub />
            </Link>
          </div>
          <NavList groups={props.groups} collapsed={false} awaiting={awaiting} onNavigate={() => setOpen(false)} />
          <SessionFooter user={props.user} sessionMode={props.sessionMode} collapsed={false} />
        </div>
      </Drawer>
    </>
  );
}

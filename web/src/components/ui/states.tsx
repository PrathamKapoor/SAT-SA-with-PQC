import { AlertOctagon, Inbox, Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function EmptyState({
  title,
  children,
  action,
  icon,
  className,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-start gap-2 rounded-md border border-dashed border-line-2 bg-canvas/60 px-5 py-6", className)}>
      <span aria-hidden="true" className="text-faint">
        {icon ?? <Inbox className="size-5" />}
      </span>
      <p className="text-[14px] font-medium text-ink">{title}</p>
      {children && <div className="max-w-xl text-[13px] leading-relaxed text-muted">{children}</div>}
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}

export function LoadingState({ label = "Loading", className }: { label?: string; className?: string }) {
  return (
    <div role="status" aria-live="polite" className={cn("flex items-center gap-2 py-6 text-[13px] text-muted", className)}>
      <Loader2 className="size-4 animate-spin" aria-hidden="true" />
      {label}
    </div>
  );
}

export function ErrorState({ title = "This could not be loaded", children, className }: { title?: string; children?: ReactNode; className?: string }) {
  return (
    <div role="alert" className={cn("flex items-start gap-3 rounded-md border border-critical/30 bg-critical-tint px-4 py-3", className)}>
      <AlertOctagon className="mt-0.5 size-4 shrink-0 text-critical" aria-hidden="true" />
      <div>
        <p className="text-[13.5px] font-medium text-critical">{title}</p>
        {children && <div className="mt-0.5 text-[13px] text-ink-2">{children}</div>}
      </div>
    </div>
  );
}

/** Loading skeleton lines for route-level loading.tsx files. */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn("animate-pulse rounded-sm bg-sunken", className)} />;
}

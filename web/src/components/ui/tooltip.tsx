import { useId, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * CSS-only tooltip. Appears on hover and on keyboard focus of the trigger;
 * the tip is linked with aria-describedby so screen readers announce it.
 * The trigger must be focusable when it carries information.
 */
export function Tooltip({
  tip,
  children,
  side = "top",
  className,
}: {
  tip: ReactNode;
  children: ReactNode;
  side?: "top" | "bottom" | "right";
  className?: string;
}) {
  const id = useId();
  return (
    <span className={cn("group/tip relative inline-flex", className)} aria-describedby={id}>
      {children}
      <span
        role="tooltip"
        id={id}
        className={cn(
          "pointer-events-none absolute z-50 w-max max-w-64 rounded-sm bg-ink px-2 py-1.5 text-[12px] leading-snug text-white opacity-0 shadow-overlay transition-opacity duration-100 group-focus-within/tip:opacity-100 group-hover/tip:opacity-100",
          side === "top" && "bottom-[calc(100%+6px)] left-1/2 -translate-x-1/2",
          side === "bottom" && "top-[calc(100%+6px)] left-1/2 -translate-x-1/2",
          side === "right" && "top-1/2 left-[calc(100%+8px)] -translate-y-1/2",
        )}
      >
        {tip}
      </span>
    </span>
  );
}

import type { ReactNode } from "react";
import { SmoothScroll } from "./SmoothScroll";

interface PageShellProps {
  /** Fixed chrome rendered before <main> (nav pill). */
  header?: ReactNode;
  children: ReactNode;
  /** Rendered after <main>; wrap it in a `sticky bottom-0 z-0` element for CA's footer reveal. */
  footer?: ReactNode;
  /** Fixed overlays rendered inside <main> after the sections (minimap, "Learn more" widget). */
  overlays?: ReactNode;
}

/**
 * CA page frame: `min-h-svh flex-col` wrapper → fixed header, `relative z-1` main (black ground,
 * first section stretches), footer revealed underneath because main scrolls over the sticky footer.
 */
export function PageShell({ header, children, footer, overlays }: PageShellProps) {
  return (
    <SmoothScroll>
      <div className="flex min-h-svh flex-col">
        {header}
        <main className="relative z-1 flex flex-1 flex-col bg-black [&>*:first-child]:flex-1">
          {children}
          {overlays}
        </main>
        {footer}
      </div>
    </SmoothScroll>
  );
}

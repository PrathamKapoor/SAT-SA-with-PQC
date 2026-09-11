import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface MarqueeProps {
  children: ReactNode;
  /** Seconds for one full loop of one copy. */
  duration?: number;
  /** Copies rendered back-to-back so the loop never shows a gap. */
  repeat?: number;
  className?: string;
}

/** Infinite left-scrolling marquee (replaces CA's `marqy`). Paused under reduced motion. */
export function Marquee({ children, duration = 20, repeat = 4, className }: MarqueeProps) {
  return (
    <div className={cn("relative w-full overflow-x-clip", className)}>
      <div className="flex" style={{ ["--marquee-duration" as string]: `${duration}s` }}>
        {Array.from({ length: repeat }, (_, i) => (
          <div key={i} data-marquee-track="true" aria-hidden={i > 0 ? true : undefined} className="flex flex-[1_0_auto] animate-marquee-left will-change-transform">
            {children}
          </div>
        ))}
      </div>
    </div>
  );
}

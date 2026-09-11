"use client";

import type { ReactNode } from "react";
import { ReactLenis } from "lenis/react";

export const easeOutExpo = (t: number) => (t === 1 ? 1 : 1 - Math.pow(2, -10 * t));

/** Root Lenis smooth scroll, configured like contentarchitecture.dev (lerp 0.1, 1.2s anchor scrolls). */
export function SmoothScroll({ children }: { children: ReactNode }) {
  return (
    <ReactLenis root options={{ allowNestedScroll: true, anchors: { duration: 1.2, easing: easeOutExpo } }}>
      {children}
    </ReactLenis>
  );
}

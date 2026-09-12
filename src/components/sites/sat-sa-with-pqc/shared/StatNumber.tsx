"use client";

import { useEffect, useRef, useState } from "react";
import { useInView, usePrefersReducedMotion } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/hooks";
import { cn } from "@/lib/utils";

interface StatNumberProps {
  /** Target value. Non-integers (e.g. 92.5) count up in the same number of decimal places. */
  value: number;
  /** Appended after the number with no space, e.g. "+" or "%". */
  suffix?: string;
  /** Count-up duration in ms. */
  duration?: number;
  className?: string;
}

/** Counts up from 0 to `value` once it enters the viewport. Shows the final value immediately
 * under reduced motion, and server-renders the final value so there's no layout jump before hydration. */
export function StatNumber({ value, suffix = "", duration = 1200, className }: StatNumberProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { threshold: 0.4 });
  const reduced = usePrefersReducedMotion();
  const [display, setDisplay] = useState(value);
  const decimals = Math.max(0, (String(value).split(".")[1] ?? "").length);

  useEffect(() => {
    if (!inView || reduced) return;
    let raf = 0;
    const ease = (t: number) => 1 - (1 - t) ** 3;
    const tick = (start: number) => (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      setDisplay(value * ease(t));
      if (t < 1) raf = requestAnimationFrame(tick(start));
    };
    raf = requestAnimationFrame((start) => {
      setDisplay(0);
      raf = requestAnimationFrame(tick(start));
    });
    return () => cancelAnimationFrame(raf);
  }, [inView, reduced, value, duration]);

  return (
    <span ref={ref} className={cn("tabular-nums", className)}>
      {display.toFixed(decimals)}
      {suffix}
    </span>
  );
}

"use client";

import { useRef, type ElementType, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { useInView } from "./hooks";

const EASE_OUT = "cubic-bezier(0.16, 1, 0.3, 1)";

interface RevealProps {
  as?: ElementType;
  children: ReactNode;
  className?: string;
  /** Delay in ms after entering the viewport. */
  delay?: number;
  /** Fade + rise from 48px (CTA/button entrance) instead of a pure opacity fade (split-line text). */
  rise?: boolean;
}

/**
 * CA entrance: split-line text fades 0→1 over ~1s ease-out when it enters the viewport; buttons
 * additionally rise from translateY(48px). Motion-safe only — reduced motion renders final state.
 */
export function Reveal({ as: Tag = "div", children, className, delay = 0, rise = false }: RevealProps) {
  const ref = useRef<HTMLElement>(null);
  // The live site reveals as soon as a block touches the viewport (text at y≈870 of 900 is shown).
  const inView = useInView(ref);
  return (
    <Tag
      ref={ref}
      className={cn(
        "motion-safe:transition-[opacity,transform] motion-safe:duration-1000",
        inView ? "opacity-100 translate-y-0" : cn("motion-safe:opacity-0", rise && "motion-safe:translate-y-48"),
        className,
      )}
      style={{ transitionTimingFunction: EASE_OUT, transitionDelay: `${delay}ms` }}
    >
      {children}
    </Tag>
  );
}

"use client";

import { useRef } from "react";
import { useInView, usePrefersReducedMotion } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/hooks";
import { StatNumber } from "./StatNumber";

interface CoverageGaugeProps {
  value: number;
  className?: string;
}

const SIZE = 128;
const STROKE = 10;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/** A single-value ring gauge (sequential brand-green fill vs a muted track), the "hero number"
 * treatment for one metric — line coverage measured by `coverage report`. */
export function CoverageGauge({ value, className }: CoverageGaugeProps) {
  const ref = useRef<SVGSVGElement>(null);
  const inView = useInView(ref, { threshold: 0.4 });
  const reduced = usePrefersReducedMotion();
  const progress = inView || reduced ? value / 100 : 0;
  const offset = CIRCUMFERENCE * (1 - progress);

  return (
    <div className={className} role="img" aria-label={`${value}% line coverage`}>
      <div className="relative inline-block" style={{ width: SIZE, height: SIZE }}>
        <svg ref={ref} width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} className="-rotate-90">
          <circle cx={SIZE / 2} cy={SIZE / 2} r={RADIUS} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={STROKE} />
          <circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={RADIUS}
            fill="none"
            stroke="#34d399"
            strokeWidth={STROKE}
            strokeLinecap="round"
            strokeDasharray={CIRCUMFERENCE}
            strokeDashoffset={offset}
            className="motion-safe:transition-[stroke-dashoffset] motion-safe:duration-1000 motion-safe:ease-out"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center" aria-hidden="true">
          <span className="font-medium text-headline-10 text-white">
            <StatNumber value={value} suffix="%" />
          </span>
        </div>
      </div>
    </div>
  );
}

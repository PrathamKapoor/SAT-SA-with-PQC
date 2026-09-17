"use client";

import { useRef } from "react";
import { useInView, usePrefersReducedMotion } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/hooks";
import { StatNumber } from "./StatNumber";

interface CoverageGaugeProps {
  value: number;
  label?: string;
  className?: string;
}

const VIEWBOX = 120;
const STROKE = 8;
const RADIUS = (VIEWBOX - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/** Single-value ring gauge. The ring and its number share one square box, so the value stays centred at any size. */
export function CoverageGauge({ value, label = "Line coverage", className }: CoverageGaugeProps) {
  const ref = useRef<SVGSVGElement>(null);
  const inView = useInView(ref, { threshold: 0.4 });
  const reduced = usePrefersReducedMotion();
  const progress = inView || reduced ? value / 100 : 0;
  const offset = CIRCUMFERENCE * (1 - progress);

  return (
    <figure className={`coverage-gauge m-0 flex flex-col items-center gap-8 ${className ?? ""}`}>
      <div className="coverage-gauge__ring relative grid aspect-square place-items-center" role="img" aria-label={`${value}% ${label.toLowerCase()}`}>
        <svg
          ref={ref}
          viewBox={`0 0 ${VIEWBOX} ${VIEWBOX}`}
          className="absolute inset-0 size-full -rotate-90"
          aria-hidden="true"
        >
          <circle cx={VIEWBOX / 2} cy={VIEWBOX / 2} r={RADIUS} fill="none" stroke="#ede9fe" strokeWidth={STROKE} />
          <circle
            cx={VIEWBOX / 2}
            cy={VIEWBOX / 2}
            r={RADIUS}
            fill="none"
            stroke="#7c3aed"
            strokeWidth={STROKE}
            strokeLinecap="round"
            strokeDasharray={CIRCUMFERENCE}
            strokeDashoffset={offset}
            className="motion-safe:transition-[stroke-dashoffset] motion-safe:duration-1000 motion-safe:ease-out"
          />
        </svg>
        <span className="coverage-gauge__value relative font-semibold leading-none tabular-nums tracking-[-0.03em] text-slate-950" aria-hidden="true">
          <StatNumber value={value} suffix="%" />
        </span>
      </div>
      <figcaption className="font-mono text-caption-10 text-slate-500 uppercase">{label}</figcaption>
    </figure>
  );
}

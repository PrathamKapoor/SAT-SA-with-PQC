"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useCallback, useId, useRef, useState } from "react";
import { buttonClass } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { STAGES, stageFor } from "./engine";
import { EvidenceFieldCanvas, type EvidenceFieldHandle } from "./EvidenceFieldCanvas";

export function EvidenceHero() {
  const field = useRef<EvidenceFieldHandle>(null);
  const [order, setOrder] = useState(0.12);
  const sliderId = useId();
  const onOrder = useCallback((o: number) => setOrder(o), []);
  const stage = stageFor(order);
  const active = STAGES.indexOf(stage);

  return (
    <section aria-labelledby="hero-title" className="relative overflow-hidden border-b border-line bg-paper">
      <div className="mx-auto grid max-w-[1440px] lg:min-h-[calc(100svh-4rem)] lg:grid-cols-[minmax(0,30rem)_minmax(0,1fr)] xl:grid-cols-[minmax(0,34rem)_minmax(0,1fr)]">
        <div className="relative z-10 flex flex-col justify-center px-5 pt-14 pb-8 md:px-8 lg:py-12 lg:pr-4 lg:pl-10 xl:pl-14 [@media(min-width:1024px)_and_(max-height:820px)]:py-7">
          <p className="label flex items-center gap-2 text-ink-2">
            <span aria-hidden="true" className="size-1.5 rounded-full bg-brand" />
            SAT-SA
          </p>
          <h1 id="hero-title" className="mt-5 text-[40px] leading-[1.02] font-semibold tracking-[-0.035em] text-ink sm:text-[48px] xl:text-[56px] [@media(min-width:1024px)_and_(max-height:820px)]:mt-4 [@media(min-width:1024px)_and_(max-height:820px)]:text-[42px]">
            Supervisory Analytics for SOC Assessment.
          </h1>
          <p className="mt-5 max-w-[34rem] text-[16px] leading-relaxed text-muted xl:text-[17px] [@media(min-width:1024px)_and_(max-height:820px)]:mt-4 [@media(min-width:1024px)_and_(max-height:820px)]:text-[15px]">
            Periodic evidence is analysed for execution gaps, missing expected evidence, anomalies and peer deviations. Human supervisors make the final decision.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3 [@media(min-width:1024px)_and_(max-height:820px)]:mt-6">
            <Link href="/login" className={buttonClass("primary", "lg")}>
              Sign in
              <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
            <Link href="/methodology" className={buttonClass("secondary", "lg")}>
              See the method
            </Link>
          </div>
          <ul className="mt-10 flex flex-wrap gap-x-5 gap-y-2 [@media(min-width:1024px)_and_(max-height:820px)]:mt-6" aria-label="Operating model">
            {["Periodic, not real-time", "Offline evidence store", "A human decides"].map((t) => (
              <li key={t} className="label flex items-center gap-1.5">
                <span aria-hidden="true" className="h-px w-3 bg-line-2" />
                {t}
              </li>
            ))}
          </ul>
        </div>

        <div className="relative flex flex-col border-t border-line lg:block lg:border-t-0 lg:border-l">
          <div className="relative h-[400px] sm:h-[460px] lg:absolute lg:inset-0 lg:h-auto">
            <EvidenceFieldCanvas
              ref={field}
              onOrder={onOrder}
              label="Interactive illustration: scattered SOC evidence records reorganising into findings and supervisory review as you move across them."
              className="absolute inset-0 lg:bottom-14"
            />
            <p className="label pointer-events-none absolute top-5 left-5 md:left-7">Fig. 01 · Evidence field</p>
            <p className="pointer-events-none absolute top-5 right-5 hidden text-[12px] text-muted md:right-7 md:block">Move across the field to organise the evidence</p>
          </div>

          <div className="relative flex flex-wrap items-end justify-between gap-x-6 gap-y-3 border-t border-line/70 bg-paper/90 px-5 py-3 backdrop-blur-sm md:px-7 lg:absolute lg:inset-x-0 lg:bottom-0">
            <ol aria-label="Analysis stage" className="flex flex-wrap items-center gap-x-1 gap-y-1">
              {STAGES.map((s, i) => (
                <li key={s} aria-current={i === active ? "step" : undefined} className="flex items-center">
                  {i > 0 && <span aria-hidden="true" className={cn("mx-1.5 h-px w-3", i <= active ? "bg-ink" : "bg-line-2")} />}
                  <span className={cn("font-mono text-[10.5px] tracking-[0.08em] uppercase", i === active ? "font-semibold text-brand-strong" : i < active ? "text-ink-2" : "text-faint")}>{s}</span>
                </li>
              ))}
            </ol>
            <div className="flex items-center gap-3">
              <label htmlFor={sliderId} className="label whitespace-nowrap">
                Organisation <span className="num text-ink">{Math.round(order * 100)}%</span>
              </label>
              <input
                id={sliderId}
                type="range"
                min={0}
                max={100}
                value={Math.round(order * 100)}
                onChange={(e) => field.current?.setTarget(Number(e.target.value) / 100)}
                className="w-24 accent-[#5236c9]"
              />
              <button type="button" onClick={() => field.current?.setTarget(1)} className="rounded-sm border border-line-2 px-2 py-1 text-[12px] font-medium text-ink hover:border-ink/40">
                Organise
              </button>
              <button type="button" onClick={() => field.current?.setTarget(0)} className="rounded-sm px-2 py-1 text-[12px] text-muted hover:bg-sunken hover:text-ink">
                Scatter
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

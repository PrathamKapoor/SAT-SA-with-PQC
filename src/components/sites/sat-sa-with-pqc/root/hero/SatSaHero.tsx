"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import { ArrowRight, Play, RotateCcw } from "lucide-react";
import { HeroVisual } from "./HeroVisual";
import type { HeroVisualHandle } from "./HeroVisual";
import { SatSaTexture } from "./SatSaTexture";
import type { Phase } from "./evidenceEngine";
import type { heroContent } from "../content/site";
import "./SatSaHero.css";

const STATUS: Record<Phase, string> = {
  raw: "Raw SOC evidence",
  analysing: "Analysing relationships",
  prioritising: "Prioritising findings",
  ready: "Findings ready for human review",
};

const STEP_INDEX: Record<Phase, number> = { raw: 0, analysing: 1, prioritising: 2, ready: 3 };

export function SatSaHero({ content }: { content: typeof heroContent }) {
  const heroRef = useRef<HTMLElement>(null);
  const copyRef = useRef<HTMLDivElement>(null);
  const controlRef = useRef<HeroVisualHandle | null>(null);
  const [phase, setPhase] = useState<Phase>("raw");
  const [playing, setPlaying] = useState(false);
  const onPhase = useCallback((next: Phase) => setPhase(next), []);
  const onPlayingChange = useCallback((next: boolean) => setPlaying(next), []);
  const activeStep = STEP_INDEX[phase];

  return (
    <section ref={heroRef} aria-labelledby="satsa-hero-title" className="satsa-hero">
      <div aria-hidden="true" className="satsa-grid-texture satsa-hero__grid" />
      <HeroVisual
        containerRef={heroRef}
        copyRef={copyRef}
        controlRef={controlRef}
        onPhase={onPhase}
        onPlayingChange={onPlayingChange}
      />
      <SatSaTexture />

      <div className="satsa-hero__inner">
        <div ref={copyRef} className="satsa-hero__copy">
          <p className="satsa-hero__eyebrow">
            <span aria-hidden="true" className="satsa-hero__dot" />
            {content.eyebrow}
          </p>

          <h1 id="satsa-hero-title" className="satsa-hero__title">
            {content.titleLines.map((line) => (
              <span key={line} className="block">
                {line}
              </span>
            ))}
          </h1>

          <p className="satsa-hero__lede">
            {content.lede.map((line) => (
              <span key={line} className="block">
                {line}
              </span>
            ))}
          </p>

          <div className="satsa-hero__actions">
            <Link href={content.primaryCta.href} className="satsa-hero__cta">
              {content.primaryCta.label}
              <ArrowRight className="size-[16px]" aria-hidden="true" />
            </Link>
            <a href={content.secondaryCta.href} className="satsa-hero__link">
              {content.secondaryCta.label}
            </a>
          </div>

          <div className="satsa-hero__instrument">
            <div className="satsa-hero__controls" role="group" aria-label="Evidence animation">
              <button
                type="button"
                className="satsa-hero__analyse is-primary"
                onClick={() => controlRef.current?.play()}
              >
                <Play className="size-[14px]" aria-hidden="true" />
                {playing ? "Playing" : phase === "ready" ? "Replay" : "Play"}
              </button>
              <button
                type="button"
                className="satsa-hero__analyse"
                onClick={() => controlRef.current?.reset()}
              >
                <RotateCcw className="size-[14px]" aria-hidden="true" />
                Reset
              </button>
            </div>
            <p className="satsa-hero__status" aria-live="polite">
              <span aria-hidden="true" className={`satsa-hero__status-dot is-${phase}`} />
              {STATUS[phase]}
            </p>
          </div>

          <ol className="satsa-hero__steps" aria-label="SAT-SA process">
            {content.steps.map((step, i) => (
              <li key={step} className={i === activeStep ? "is-active" : i < activeStep ? "is-done" : undefined} aria-current={i === activeStep ? "step" : undefined}>
                {i > 0 && <ArrowRight className="satsa-hero__step-arrow" aria-hidden="true" />}
                {step}
              </li>
            ))}
          </ol>

          <p className="satsa-hero__hint">
            <span className="satsa-hero__hint-pointer">Press Play, or rearrange it yourself: move through the evidence and press and hold.</span>
            <span className="satsa-hero__hint-touch">Press Play, or press and hold the evidence to rearrange it.</span>
          </p>
        </div>
      </div>
    </section>
  );
}

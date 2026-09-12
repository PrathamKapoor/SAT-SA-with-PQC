"use client";

import React, { useEffect, useRef } from "react";
import "./InteractiveEvidenceHero.css";

export function InteractiveEvidenceHero() {
  const rootRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef<number | null>(null);
  const pointerRef = useRef({ x: 0.5, y: 0.5 });

  useEffect(() => () => {
    if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
  }, []);

  const paintPointer = () => {
    const root = rootRef.current;
    if (!root) return;

    const { x, y } = pointerRef.current;
    root.style.setProperty("--hero-pointer-x", `${x * 100}%`);
    root.style.setProperty("--hero-pointer-y", `${y * 100}%`);
    root.style.setProperty("--hero-tilt-x", `${(x - 0.5) * 5}deg`);
    root.style.setProperty("--hero-tilt-y", `${(0.5 - y) * 4}deg`);
    frameRef.current = null;
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const root = rootRef.current;
    if (!root) return;

    const rect = root.getBoundingClientRect();
    pointerRef.current = {
      x: Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width)),
      y: Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height)),
    };

    if (frameRef.current === null) {
      frameRef.current = requestAnimationFrame(paintPointer);
    }
  };

  const handlePointerLeave = () => {
    pointerRef.current = { x: 0.5, y: 0.5 };
    if (frameRef.current === null) {
      frameRef.current = requestAnimationFrame(paintPointer);
    }
  };

  return (
    <div
      ref={rootRef}
      data-evidence-flow="true"
      data-interactive-hero="true"
      aria-hidden="true"
      className="interactive-evidence-hero"
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
    >
      <div className="interactive-evidence-hero__glow" />
      <div className="interactive-evidence-hero__grid" />

      <div className="interactive-evidence-hero__scene">
        <svg viewBox="0 0 680 480" fill="none" className="interactive-evidence-hero__map">
          <path className="interactive-evidence-hero__path interactive-evidence-hero__path--one" d="M58 246C155 246 188 116 310 116S448 240 620 240" />
          <path className="interactive-evidence-hero__path interactive-evidence-hero__path--two" d="M58 246C168 246 212 372 352 372S480 240 620 240" />
          <path className="interactive-evidence-hero__path interactive-evidence-hero__path--three" d="M310 116C354 190 354 286 352 372" />

          <circle className="interactive-evidence-hero__orbit" cx="58" cy="246" r="48" />
          <circle className="interactive-evidence-hero__orbit interactive-evidence-hero__orbit--analysis" cx="331" cy="244" r="94" />
          <circle className="interactive-evidence-hero__orbit interactive-evidence-hero__orbit--decision" cx="620" cy="240" r="62" />

          <circle className="interactive-evidence-hero__node interactive-evidence-hero__node--evidence" cx="58" cy="246" r="9" />
          <circle className="interactive-evidence-hero__node interactive-evidence-hero__node--signal" cx="310" cy="116" r="12" />
          <circle className="interactive-evidence-hero__node interactive-evidence-hero__node--signal" cx="352" cy="372" r="10" />
          <circle className="interactive-evidence-hero__node interactive-evidence-hero__node--decision" cx="620" cy="240" r="17" />
        </svg>

        <div className="interactive-evidence-hero__core">
          <span>Corroborated</span>
          <strong>Supervisory intelligence</strong>
          <small>Traceable evidence chain</small>
        </div>

        <div data-flow-stage="evidence" className="interactive-evidence-hero__stage interactive-evidence-hero__stage--evidence">
          <span>01</span>
          Evidence
        </div>
        <div data-flow-stage="analysis" className="interactive-evidence-hero__stage interactive-evidence-hero__stage--analysis">
          <span>02</span>
          Analysis
        </div>
        <div data-flow-stage="decision" className="interactive-evidence-hero__stage interactive-evidence-hero__stage--decision">
          <span>03</span>
          Examiner decision
        </div>
      </div>
    </div>
  );
}

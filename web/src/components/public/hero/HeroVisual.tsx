"use client";

import { useCallback, useEffect, useImperativeHandle, useRef } from "react";
import type { RefObject } from "react";
import { EvidenceEngine } from "./evidenceEngine";
import type { Phase, PointerState, Rect } from "./evidenceEngine";

export interface HeroVisualHandle {
  play: () => void;
  reset: () => void;
}

interface HeroVisualProps {
  containerRef: RefObject<HTMLElement | null>;
  copyRef: RefObject<HTMLElement | null>;
  controlRef: RefObject<HeroVisualHandle | null>;
  onPhase: (phase: Phase) => void;
  onPlayingChange: (playing: boolean) => void;
}

const AUTO_PERIOD = 12;
const PLAY_REWIND_SPEED = 1.8;
const PLAY_FORWARD_SPEED = 1.15;
const RESET_SPEED = 2;
const INTERACTIVE = "a, button, input, select, textarea, label, [role='button']";

/** Auto demonstration until the visitor takes over: raw, then analyse, hold, then relax. */
function autoTarget(seconds: number) {
  const t = seconds % AUTO_PERIOD;
  if (t < 1.5) return 0;
  if (t < 9) return 1;
  return 0;
}

type PlayStage = "rewind" | "forward" | null;

export function HeroVisual({ containerRef, copyRef, controlRef, onPhase, onPlayingChange }: HeroVisualProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const onPhaseRef = useRef(onPhase);
  const userTargetRef = useRef<number | null>(null);
  const requestDrawRef = useRef<() => void>(() => {});
  const playRef = useRef<PlayStage>(null);
  const speedRef = useRef(1);
  const onPlayingRef = useRef(onPlayingChange);

  useEffect(() => {
    onPhaseRef.current = onPhase;
    onPlayingRef.current = onPlayingChange;
  }, [onPhase, onPlayingChange]);

  const setPlay = useCallback((stage: PlayStage) => {
    const was = playRef.current !== null;
    playRef.current = stage;
    if (was !== (stage !== null)) onPlayingRef.current(stage !== null);
  }, []);

  useImperativeHandle(controlRef, () => ({
    play: () => {
      userTargetRef.current = 1;
      setPlay("rewind");
      requestDrawRef.current();
    },
    reset: () => {
      setPlay(null);
      userTargetRef.current = 0;
      speedRef.current = RESET_SPEED;
      requestDrawRef.current();
    },
  }));

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    let reduced = motionQuery.matches;
    const pointer: PointerState = { x: -9999, y: -9999, inside: false, down: false, dx: 0, dy: 0 };
    let width = 0;
    let height = 0;
    let engine: EvidenceEngine | null = null;
    let frame = 0;
    let running = false;
    let visible = true;
    let last = performance.now();
    const start = last;
    let lastPhase: Phase | null = null;
    let scrollFloor = 0;

    const measureSafe = (): Rect | null => {
      const copy = copyRef.current;
      if (!copy) return null;
      const c = container.getBoundingClientRect();
      const r = copy.getBoundingClientRect();
      return { x: r.left - c.left, y: r.top - c.top, w: r.width, h: r.height };
    };

    const resize = () => {
      const rect = container.getBoundingClientRect();
      width = rect.width;
      height = rect.height;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const safe = measureSafe();
      if (!engine) {
        engine = new EvidenceEngine(width, height, safe);
        const mono = getComputedStyle(document.documentElement).getPropertyValue("--font-geist-mono");
        engine.setFont(`${mono.trim() || ""}${mono.trim() ? ", " : ""}ui-monospace, monospace`);
      } else {
        engine.resize(width, height, safe);
      }
      if (reduced) paintStatic();
    };

    const publish = () => {
      if (!engine) return;
      container.style.setProperty("--hero-analysis", engine.analysis.toFixed(3));
      const phase = engine.phase;
      if (phase !== lastPhase) {
        lastPhase = phase;
        onPhaseRef.current(phase);
      }
    };

    const chooseTarget = (now: number) => {
      if (!engine) return;
      const stage = playRef.current;
      if (stage === "rewind") {
        engine.speed = PLAY_REWIND_SPEED;
        engine.target = 0;
        if (engine.analysis < 0.03) setPlay("forward");
        return;
      }
      if (stage === "forward") {
        engine.speed = PLAY_FORWARD_SPEED;
        engine.target = 1;
        if (engine.analysis > 0.995) {
          setPlay(null);
          speedRef.current = 1;
        }
        return;
      }
      const base = userTargetRef.current ?? autoTarget((now - start) / 1000);
      engine.target = Math.max(base, scrollFloor);
      engine.speed = speedRef.current;
      if (Math.abs(engine.target - engine.analysis) < 0.01) speedRef.current = 1;
    };

    const paintStatic = () => {
      if (!engine) return;
      if (playRef.current) setPlay(null);
      engine.target = userTargetRef.current ?? 1;
      engine.step(16, { ...pointer, inside: false, down: false }, true);
      engine.draw(ctx, { ...pointer, inside: false }, true);
      publish();
    };

    const loop = (now: number) => {
      frame = requestAnimationFrame(loop);
      if (!engine) return;
      const dt = Math.min(now - last, 64);
      last = now;
      if (pointer.down && userTargetRef.current !== null) {
        userTargetRef.current = Math.min(1, userTargetRef.current + 0.011 * (dt / 16.67));
      }
      chooseTarget(now);
      engine.step(dt, pointer, false);
      engine.draw(ctx, pointer, false);
      pointer.dx = 0;
      pointer.dy = 0;
      publish();
    };

    const startLoop = () => {
      if (running || reduced || !visible) return;
      running = true;
      last = performance.now();
      frame = requestAnimationFrame(loop);
    };
    const stopLoop = () => {
      running = false;
      cancelAnimationFrame(frame);
    };

    requestDrawRef.current = () => {
      if (reduced) paintStatic();
    };

    const takeOver = () => {
      if (userTargetRef.current === null && engine) userTargetRef.current = engine.analysis;
    };

    const toLocal = (e: PointerEvent) => {
      const rect = container.getBoundingClientRect();
      return { x: e.clientX - rect.left, y: e.clientY - rect.top };
    };

    const onMove = (e: PointerEvent) => {
      if (reduced) return;
      const p = toLocal(e);
      if (pointer.inside) {
        pointer.dx += p.x - pointer.x;
        pointer.dy += p.y - pointer.y;
        const moved = Math.hypot(p.x - pointer.x, p.y - pointer.y);
        if (e.pointerType === "mouse" && moved > 0 && playRef.current === null) {
          takeOver();
          if (userTargetRef.current !== null && userTargetRef.current < 0.58) {
            userTargetRef.current = Math.min(0.58, userTargetRef.current + moved * 0.00045);
          }
        }
      }
      pointer.x = p.x;
      pointer.y = p.y;
      pointer.inside = true;
    };
    const onLeave = () => {
      pointer.inside = false;
      pointer.down = false;
    };
    const onDown = (e: PointerEvent) => {
      if (reduced) return;
      const target = e.target as Element | null;
      if (target?.closest(INTERACTIVE)) return;
      const p = toLocal(e);
      pointer.x = p.x;
      pointer.y = p.y;
      pointer.inside = true;
      pointer.down = true;
      if (playRef.current !== null) {
        setPlay(null);
        speedRef.current = 1;
        userTargetRef.current = engine ? engine.analysis : 0;
      }
      takeOver();
    };
    const onUp = () => {
      if (!pointer.down) return;
      pointer.down = false;
      if (engine && userTargetRef.current !== null && engine.analysis > 0.4) userTargetRef.current = 1;
    };
    const onScroll = () => {
      const rect = container.getBoundingClientRect();
      const progress = Math.min(1, Math.max(0, -rect.top / (rect.height * 0.45)));
      scrollFloor = progress;
    };

    const onMotionChange = () => {
      reduced = motionQuery.matches;
      if (reduced) {
        stopLoop();
        paintStatic();
      } else {
        startLoop();
      }
    };

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(container);
    const intersection = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      if (visible) startLoop();
      else stopLoop();
    });
    intersection.observe(container);

    resize();
    onScroll();
    if (reduced) paintStatic();
    else startLoop();

    container.addEventListener("pointermove", onMove);
    container.addEventListener("pointerleave", onLeave);
    container.addEventListener("pointerdown", onDown);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
    window.addEventListener("scroll", onScroll, { passive: true });
    motionQuery.addEventListener("change", onMotionChange);

    return () => {
      stopLoop();
      resizeObserver.disconnect();
      intersection.disconnect();
      container.removeEventListener("pointermove", onMove);
      container.removeEventListener("pointerleave", onLeave);
      container.removeEventListener("pointerdown", onDown);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
      window.removeEventListener("scroll", onScroll);
      motionQuery.removeEventListener("change", onMotionChange);
      requestDrawRef.current = () => {};
    };
  }, [containerRef, copyRef, setPlay]);

  return <canvas ref={canvasRef} aria-hidden="true" className="satsa-hero-canvas pointer-events-none absolute inset-0 block" />;
}

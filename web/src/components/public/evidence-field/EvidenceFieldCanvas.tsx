"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import { cn } from "@/lib/utils";
import { EvidenceField } from "./engine";

export interface EvidenceFieldHandle {
  /** Set the target organisation in [0, 1] (keyboard, buttons). */
  setTarget: (v: number) => void;
}

interface Props {
  className?: string;
  density?: "full" | "medium" | "compact";
  /** Called at most ~10 times a second with the current order in [0, 1]. */
  onOrder?: (order: number) => void;
  /** Resting organisation before anyone interacts. */
  initial?: number;
  label: string;
}

const IDLE_SECONDS = 6;

/**
 * Canvas host for the evidence field. Pointer handling is confined to this
 * element; the canvas never covers page text or navigation.
 */
export const EvidenceFieldCanvas = forwardRef<EvidenceFieldHandle, Props>(function EvidenceFieldCanvas(
  { className, density, onOrder, initial = 0.12, label },
  ref,
) {
  const hostRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const engineRef = useRef<EvidenceField | null>(null);
  const manualUntil = useRef(0);
  const lastInteract = useRef(0);
  const onOrderRef = useRef(onOrder);

  useEffect(() => {
    onOrderRef.current = onOrder;
  }, [onOrder]);

  useImperativeHandle(ref, () => ({
    setTarget: (v: number) => {
      const e = engineRef.current;
      if (!e) return;
      e.target = Math.max(0, Math.min(1, v));
      manualUntil.current = performance.now() / 1000 + 12;
      lastInteract.current = performance.now() / 1000;
    },
  }));

  useEffect(() => {
    const host = hostRef.current;
    const canvas = canvasRef.current;
    if (!host || !canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reducedQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    let reduced = reducedQuery.matches;
    const pointer = { x: 0, y: 0, inside: false, down: false };
    let visible = true;
    let frame = 0;
    let last = performance.now();
    let lastReport = 0;

    const pickDensity = (w: number) => density ?? (w < 520 ? "compact" : w < 900 ? "medium" : "full");

    const size = () => {
      const r = host.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.max(1, Math.round(r.width * dpr));
      canvas.height = Math.max(1, Math.round(r.height * dpr));
      canvas.style.width = `${r.width}px`;
      canvas.style.height = `${r.height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      if (!engineRef.current) {
        engineRef.current = new EvidenceField(r.width, r.height, pickDensity(r.width));
        engineRef.current.order = engineRef.current.target = reduced ? Math.max(initial, 0.6) : initial;
      } else engineRef.current.resize(r.width, r.height);
      engineRef.current.step(0.016, pointer, true);
      engineRef.current.draw(ctx, true);
    };

    const tick = (now: number) => {
      const e = engineRef.current;
      if (!e) return;
      const dt = (now - last) / 1000;
      last = now;
      const t = now / 1000;
      if (pointer.down) {
        e.target = Math.min(1, e.target + dt * 0.55);
        lastInteract.current = t;
      }
      if (t > manualUntil.current && t - lastInteract.current > IDLE_SECONDS && e.target > initial) {
        e.target = Math.max(initial, e.target - dt * 0.035);
      }
      e.step(dt, pointer, reduced);
      e.draw(ctx, reduced);
      if (now - lastReport > 100) {
        lastReport = now;
        onOrderRef.current?.(e.order);
        host.dataset.order = e.order.toFixed(2);
      }
      frame = visible && !reduced ? requestAnimationFrame(tick) : 0;
    };

    const start = () => {
      if (frame || reduced || !visible) return;
      last = performance.now();
      frame = requestAnimationFrame(tick);
    };
    const redrawOnce = () => {
      const e = engineRef.current;
      if (!e) return;
      e.step(0.016, pointer, true);
      e.draw(ctx, true);
      onOrderRef.current?.(e.order);
    };

    const local = (ev: PointerEvent) => {
      const r = canvas.getBoundingClientRect();
      return { x: ev.clientX - r.left, y: ev.clientY - r.top };
    };
    const onMove = (ev: PointerEvent) => {
      const p = local(ev);
      const e = engineRef.current;
      if (e && pointer.inside) {
        const dist = Math.hypot(p.x - pointer.x, p.y - pointer.y);
        const diag = Math.hypot(canvas.clientWidth, canvas.clientHeight);
        if (dist < diag * 0.25) e.target = Math.min(1, e.target + dist / (diag * 2.4));
      }
      pointer.x = p.x;
      pointer.y = p.y;
      pointer.inside = true;
      lastInteract.current = performance.now() / 1000;
      if (reduced) redrawOnce();
    };
    const onLeave = () => {
      pointer.inside = false;
      pointer.down = false;
    };
    const onDown = (ev: PointerEvent) => {
      if (ev.pointerType === "mouse" && ev.button !== 0) return;
      pointer.down = true;
      onMove(ev);
    };
    const onUp = () => {
      pointer.down = false;
      if (reduced && engineRef.current) {
        engineRef.current.target = Math.min(1, engineRef.current.target + 0.2);
        redrawOnce();
      }
    };

    const ro = new ResizeObserver(size);
    ro.observe(host);
    const io = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting && document.visibilityState === "visible";
      if (visible) start();
    });
    io.observe(host);
    const onVisibility = () => {
      visible = document.visibilityState === "visible";
      if (visible) start();
    };
    const onMotion = () => {
      reduced = reducedQuery.matches;
      if (reduced) redrawOnce();
      else start();
    };

    host.addEventListener("pointermove", onMove);
    host.addEventListener("pointerleave", onLeave);
    host.addEventListener("pointerdown", onDown);
    window.addEventListener("pointerup", onUp);
    document.addEventListener("visibilitychange", onVisibility);
    reducedQuery.addEventListener("change", onMotion);
    size();
    start();

    // Keyboard and button changes need a redraw even when reduced motion stops the loop.
    const poll = reduced ? window.setInterval(redrawOnce, 250) : 0;

    return () => {
      cancelAnimationFrame(frame);
      window.clearInterval(poll);
      ro.disconnect();
      io.disconnect();
      host.removeEventListener("pointermove", onMove);
      host.removeEventListener("pointerleave", onLeave);
      host.removeEventListener("pointerdown", onDown);
      window.removeEventListener("pointerup", onUp);
      document.removeEventListener("visibilitychange", onVisibility);
      reducedQuery.removeEventListener("change", onMotion);
    };
  }, [density, initial]);

  return (
    <div ref={hostRef} role="img" aria-label={label} className={cn("relative touch-pan-y select-none", className)}>
      <canvas ref={canvasRef} className="absolute inset-0 block" />
    </div>
  );
});

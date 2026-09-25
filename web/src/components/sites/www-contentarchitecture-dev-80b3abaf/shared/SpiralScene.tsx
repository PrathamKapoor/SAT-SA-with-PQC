"use client";

import { useEffect, useRef, useState } from "react";
import { useLenis } from "lenis/react";
import { cn } from "@/lib/utils";
import { CursorLabel, setupCursorTracking } from "./CursorLabel";
import { useIsTouchDevice, usePrefersReducedMotion } from "./hooks";
import {
  MAX_RIPPLES,
  RING_COUNT,
  RIPPLE_DURATION,
  RIPPLE_HALF_WIDTH,
  RIPPLE_MAX_RADIUS,
  buildSpiralModel,
  createSpiralRenderer,
  drawSpiralAtlas,
  maxSpiralBufferSize,
  smoothstep,
  spiralAtlasFont,
  type SpiralFrame,
} from "./spiral-scene-gl";

export interface SpiralSceneProps {
  /** Text laid along the rings; a "." renders as a dot. CA: "THE CONTENT ARCHITECTURE." */
  phrase?: string;
  className?: string;
  /** Cursor label copy for each hold state (CA defaults). */
  labels?: Partial<SpiralSceneLabels>;
}

export interface SpiralSceneLabels {
  idle: string;
  idleTouch: string;
  holding: string;
  charged: string;
}

const DEFAULT_PHRASE = "THE CONTENT ARCHITECTURE.";
const DEFAULT_LABELS: SpiralSceneLabels = {
  idle: "Click & hold",
  idleTouch: "Tap & hold",
  holding: "Keep holding",
  charged: "Release",
};
const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";
/** Entrance fully revealed (last arrival 1.8s + 0.5s fade). */
const STATIC_TIME = 2.3;
const RESIZE_DEBOUNCE_MS = 150;

type HoldState = "idle" | "holding" | "charged";

interface Ripple {
  start: number;
  strength: number;
}

/**
 * WebGL2 hero scene: 30 counter-rotating rings of tangent glyphs spelling `phrase`, bright
 * arcs over a dotted field. Hover dissolves glyphs into dots; press-and-hold charges the rings
 * (gather + glitch + rotation freeze) and releasing sends a ripple outwards. Scroll velocity
 * (Lenis) spins the rings.
 */
export function SpiralScene({ phrase = DEFAULT_PHRASE, className, labels }: SpiralSceneProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const labelRef = useRef<HTMLDivElement>(null);
  const velocityRef = useRef(0);
  const reducedRef = useRef(false);
  const syncMotionRef = useRef<(() => void) | null>(null);
  const [isHovering, setIsHovering] = useState(false);
  const [holdState, setHoldState] = useState<HoldState>("idle");
  const touch = useIsTouchDevice();
  const reduced = usePrefersReducedMotion();

  useLenis((lenis) => {
    velocityRef.current = lenis.velocity;
  });

  useEffect(() => {
    reducedRef.current = reduced;
    syncMotionRef.current?.();
  }, [reduced]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const canvas = document.createElement("canvas");
    canvas.className = "pointer-events-none absolute inset-0 block size-full";
    canvas.setAttribute("aria-hidden", "true");
    const gl = canvas.getContext("webgl2", { alpha: false, antialias: false, depth: false, stencil: false, premultipliedAlpha: false });
    if (!gl) return; // Fallback: keep the plain #232323 container.
    const renderer = createSpiralRenderer(gl);
    if (!renderer) {
      gl.getExtension("WEBGL_lose_context")?.loseContext();
      return;
    }
    container.appendChild(canvas);

    const controller = new AbortController();
    const { signal } = controller;
    let disposed = false;
    let contextLost = false;

    // --- Model + atlas ---------------------------------------------------------------------
    const model = buildSpiralModel(phrase || DEFAULT_PHRASE);
    renderer.uploadInstances(model.instances);
    const atlasCanvas = document.createElement("canvas");
    const fontFamily = getComputedStyle(document.documentElement).getPropertyValue("--font-geist-mono").trim() || "ui-monospace, monospace";
    let atlasGrid = { columns: 8, rows: 1 };
    const renderAtlas = () => {
      const grid = drawSpiralAtlas(atlasCanvas, model.atlasChars, fontFamily);
      if (!grid) return;
      atlasGrid = grid;
      renderer.uploadAtlas(atlasCanvas);
    };
    renderAtlas();

    // --- Simulation state ------------------------------------------------------------------
    reducedRef.current = window.matchMedia(REDUCED_MOTION_QUERY).matches;
    let time = reducedRef.current ? STATIC_TIME : 0;
    let ripples: Ripple[] = reducedRef.current ? [] : [{ start: 0, strength: 1 }];
    let hold: HoldState = "idle";
    let charge = 0;
    let creep = 0;
    let releaseStart = Number.NEGATIVE_INFINITY;
    let hoverTarget = 0;
    let mouseInfluence = 0;
    const mouseTarget: [number, number] = [0, 0];
    const mouse: [number, number] = [0, 0];
    let spin = 0;
    const ringO = new Float32Array(RING_COUNT);
    const ringN = new Float32Array(RING_COUNT);
    const frozen = new Float32Array(RING_COUNT);
    const angVel = new Float32Array(RING_COUNT);
    const smoothed = new Float32Array(RING_COUNT);
    const ringUniforms = new Float32Array(RING_COUNT * 4);
    const rippleUniforms = new Float32Array(MAX_RIPPLES * 4);

    const setHold = (next: HoldState) => {
      if (hold === next) return;
      hold = next;
      setHoldState(next);
    };

    // --- Size ------------------------------------------------------------------------------
    let cssWidth = 1;
    let cssHeight = 1;
    const maxBuffer = maxSpiralBufferSize(gl);
    const applySize = () => {
      const rect = container.getBoundingClientRect();
      cssWidth = Math.max(1, rect.width);
      cssHeight = Math.max(1, rect.height);
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const width = Math.min(maxBuffer, Math.max(1, Math.round(cssWidth * dpr)));
      const height = Math.min(maxBuffer, Math.max(1, Math.round(cssHeight * dpr)));
      if (canvas.width !== width) canvas.width = width;
      if (canvas.height !== height) canvas.height = height;
    };
    const fit = (): [number, number] => {
      const aspect = cssWidth / cssHeight;
      return aspect >= 1 ? [1, aspect] : [1 / aspect, 1];
    };
    /** Container px → design units. */
    const toDesign = (x: number, y: number, out: [number, number]) => {
      const [fx, fy] = fit();
      out[0] = (x / cssWidth) * 2 - 1;
      out[1] = -((y / cssHeight) * 2 - 1);
      out[0] /= fx;
      out[1] /= fy;
    };
    applySize();

    // --- Frame -----------------------------------------------------------------------------
    const frame: SpiralFrame = {
      time,
      fit: [1, 1],
      mouse,
      mouseInfluence: 0,
      ripples: rippleUniforms,
      rippleCount: 0,
      rings: ringUniforms,
      atlasColumns: 8,
      atlasRows: 1,
      dotIndex: model.dotIndex,
    };

    const step = (dt: number) => {
      time += dt;
      ripples = ripples.filter((r) => time - r.start < RIPPLE_DURATION);

      mouseInfluence += (hoverTarget - mouseInfluence) * (1 - Math.exp(-6 * dt));
      const mouseEase = 1 - Math.exp(-14 * dt);
      mouse[0] += (mouseTarget[0] - mouse[0]) * mouseEase;
      mouse[1] += (mouseTarget[1] - mouse[1]) * mouseEase;

      const holding = hold !== "idle";
      if (holding) {
        charge = Math.min(1, charge + dt / 0.9);
        creep = 1 - (1 - creep) * Math.exp(-dt / 4);
        if (hold === "holding" && charge >= 1) setHold("charged");
      } else {
        const decay = Math.exp(-10 * dt);
        charge *= decay;
        creep *= decay;
      }

      velocityRef.current *= Math.exp(-5 * dt);
      spin += (Math.min(40, Math.abs(velocityRef.current)) - spin) * (1 - Math.exp(-4 * dt));

      const releaseElapsed = time - releaseStart;
      const releaseRunning = releaseElapsed < RIPPLE_DURATION;
      const wavefront = RIPPLE_MAX_RADIUS * smoothstep(0, 1, releaseElapsed / RIPPLE_DURATION) + RIPPLE_HALF_WIDTH;
      const follow = 1 - Math.exp(-14 * dt);
      const decay = Math.exp(-10 * dt);
      const settle = 1 - Math.exp(-3 * dt);
      const gatherTarget = smoothstep(0, 1, charge) * creep;
      for (let k = 0; k < RING_COUNT; k++) {
        const ring = model.rings[k];
        if (!ring) continue;
        let o = ringO[k] ?? 0;
        let n = ringN[k] ?? 0;
        if (holding) {
          o += (charge - o) * follow;
          n += (gatherTarget - n) * follow;
        } else if (!releaseRunning || wavefront > ring.radius) {
          o *= decay;
          n *= decay;
        }
        ringO[k] = o;
        ringN[k] = n;
        const ringCharge = smoothstep(0, 1, o);
        frozen[k] = (frozen[k] ?? 0) - ringCharge * ring.speed * dt;

        let kick = 0;
        for (const r of ripples) {
          const t = (time - r.start) / RIPPLE_DURATION;
          const bell = 1 - smoothstep(0, RIPPLE_HALF_WIDTH, Math.abs(ring.radius - RIPPLE_MAX_RADIUS * smoothstep(0, 1, t)));
          const life = smoothstep(0, 0.22, t) * (1 - smoothstep(0.78, 1, t));
          kick = Math.max(kick, bell * life * r.strength);
        }
        const av = (angVel[k] ?? 0) + (0.55 * kick * Math.sign(ring.speed) + ring.speed * spin) * dt;
        angVel[k] = av;
        const sm = (smoothed[k] ?? 0) + (av - (smoothed[k] ?? 0)) * settle;
        smoothed[k] = sm;

        ringUniforms[k * 4] = sm + (frozen[k] ?? 0);
        ringUniforms[k * 4 + 1] = ringCharge;
        ringUniforms[k * 4 + 2] = n;
      }
    };

    const render = () => {
      if (disposed || contextLost) return;
      const count = Math.min(MAX_RIPPLES, ripples.length);
      for (let i = 0; i < count; i++) {
        const r = ripples[ripples.length - count + i];
        if (!r) continue;
        rippleUniforms[i * 4] = time - r.start;
        rippleUniforms[i * 4 + 1] = r.strength;
      }
      frame.time = time;
      frame.fit = fit();
      frame.mouseInfluence = mouseInfluence;
      frame.rippleCount = count;
      frame.atlasColumns = atlasGrid.columns;
      frame.atlasRows = atlasGrid.rows;
      renderer.draw(frame, canvas.width, canvas.height);
    };

    // --- Loop ------------------------------------------------------------------------------
    let intersecting = false;
    let rafId = 0;
    let lastTs: number | null = null;
    const shouldRun = () => intersecting && !document.hidden && !reducedRef.current && !contextLost && !disposed;
    const tick = (ts: number) => {
      rafId = 0;
      if (!shouldRun()) {
        lastTs = null;
        return;
      }
      const dt = lastTs === null ? 0 : Math.min(0.05, Math.max(0, (ts - lastTs) / 1000));
      lastTs = ts;
      step(dt);
      render();
      rafId = requestAnimationFrame(tick);
    };
    const syncMotion = () => {
      if (disposed) return;
      if (reducedRef.current) {
        // Static, fully revealed frame; interactions are inert.
        time = Math.max(time, STATIC_TIME);
        ripples = [];
        hoverTarget = 0;
        mouseInfluence = 0;
        setHold("idle");
      }
      if (shouldRun()) {
        if (!rafId) {
          lastTs = null;
          rafId = requestAnimationFrame(tick);
        }
      } else {
        if (rafId) cancelAnimationFrame(rafId);
        rafId = 0;
        lastTs = null;
        render();
      }
    };
    syncMotionRef.current = syncMotion;
    /** Redraw once when the loop is paused (resize, atlas refresh). */
    const drawIfIdle = () => {
      if (!rafId) render();
    };

    const intersection = new IntersectionObserver(
      ([entry]) => {
        if (!entry) return;
        intersecting = entry.isIntersecting;
        syncMotion();
      },
      { threshold: 0 },
    );
    intersection.observe(container);
    document.addEventListener("visibilitychange", syncMotion, { signal });

    let resizeTimer: ReturnType<typeof setTimeout> | undefined;
    const resize = new ResizeObserver(() => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        if (disposed) return;
        applySize();
        drawIfIdle();
      }, RESIZE_DEBOUNCE_MS);
    });
    resize.observe(container);

    canvas.addEventListener(
      "webglcontextlost",
      () => {
        contextLost = true;
        if (rafId) cancelAnimationFrame(rafId);
        rafId = 0;
      },
      { signal },
    );

    const font = spiralAtlasFont(fontFamily);
    Promise.all([document.fonts.load(font).catch(() => []), document.fonts.ready])
      .then(() => {
        if (disposed || contextLost) return;
        renderAtlas();
        drawIfIdle();
      })
      .catch(() => {});

    // --- Pointer ---------------------------------------------------------------------------
    const interactive = () => !reducedRef.current;
    setupCursorTracking({
      container,
      signal,
      labelRef,
      setIsHovering,
      onPointerEnter: (x, y) => {
        toDesign(x, y, mouseTarget);
        if (mouseInfluence < 0.01) {
          mouse[0] = mouseTarget[0];
          mouse[1] = mouseTarget[1];
        }
        if (interactive()) hoverTarget = 1;
      },
      onPointerMove: (x, y) => {
        toDesign(x, y, mouseTarget);
        if (interactive()) hoverTarget = 1;
      },
      onPointerLeave: () => {
        hoverTarget = 0;
        setHold("idle");
      },
      onPointerDown: (x, y) => {
        if (!interactive()) return;
        toDesign(x, y, mouseTarget);
        hoverTarget = 1;
        setHold(charge >= 1 ? "charged" : "holding");
      },
      onPointerUp: () => {
        if (hold === "charged") {
          ripples.push({ start: time, strength: 0.7 + 0.6 * creep });
          if (ripples.length > MAX_RIPPLES) ripples.shift();
          releaseStart = time;
        }
        setHold("idle");
      },
    });
    container.addEventListener(
      "contextmenu",
      (e) => {
        if (hold !== "idle") e.preventDefault();
      },
      { signal },
    );

    render();

    return () => {
      disposed = true;
      syncMotionRef.current = null;
      controller.abort();
      if (rafId) cancelAnimationFrame(rafId);
      clearTimeout(resizeTimer);
      intersection.disconnect();
      resize.disconnect();
      renderer.dispose();
      gl.getExtension("WEBGL_lose_context")?.loseContext();
      canvas.remove();
      setHoldState("idle");
    };
  }, [phrase]);

  const copy = { ...DEFAULT_LABELS, ...labels };
  const label = holdState === "charged" ? copy.charged : holdState === "holding" ? copy.holding : touch ? copy.idleTouch : copy.idle;

  return (
    <div ref={containerRef} aria-hidden="true" className={cn("relative size-full cursor-pointer select-none overflow-hidden bg-black", className)}>
      <CursorLabel labelRef={labelRef} isHovering={isHovering} text={label} />
    </div>
  );
}

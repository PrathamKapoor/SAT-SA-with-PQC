"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { useElementSize, useInView } from "./hooks";

/** Density ramp, sparse → dense. */
const RAMP = ".:-=+*#%@";

export interface AsciiGrid {
  /** One char per cell, row-major; level = charCode - 33 (0 … levels-1). */
  cells: string;
  levels: number;
  cols: number;
  rows: number;
  /** width / height of the rendered box. */
  aspect: number;
}

interface AsciiImageProps extends AsciiGrid {
  /** Force the mapping; by default it follows the nearest opaque ancestor background (dark → invert). */
  invert?: boolean;
  label?: string;
  className?: string;
}

function parseRgb(value: string) {
  const m = /rgba?\(([^)]+)\)/.exec(value);
  if (!m?.[1]) return null;
  const [r = 0, g = 0, b = 0, a = 1] = m[1].split(/[\s,/]+/).filter(Boolean).map(Number);
  return { r, g, b, a };
}

/** Relative luminance (0–1) of the first ancestor with an opaque background. */
function backgroundLuminance(el: Element | null) {
  let node: Element | null = el;
  while (node) {
    const c = parseRgb(getComputedStyle(node).backgroundColor);
    if (c && c.a > 0) return (0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b) / 255;
    node = node.parentElement;
  }
  return 1;
}

function monoFont(sizePx: number) {
  const family = getComputedStyle(document.documentElement).getPropertyValue("--font-geist-mono").trim() || "ui-monospace, monospace";
  return `400 ${sizePx}px ${family}`;
}

/**
 * Pre-computed luminance grid drawn as monospace glyphs on a canvas (CA's showcase + avatars).
 * Glyph = RAMP[level], alpha = 0.12 + 0.88·n^0.85. Lazily drawn within 400px of the viewport,
 * then fades in (opacity 500ms ease-out).
 */
export function AsciiImage({ cells, levels, cols, rows, aspect, invert, label, className }: AsciiImageProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const near = useInView(wrapRef, { rootMargin: "400px" });
  const { width } = useElementSize(wrapRef);
  const [drawn, setDrawn] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !near || width <= 0) return;
    let cancelled = false;
    const draw = () => {
      if (cancelled) return;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = Math.max(1, Math.round(width * dpr));
      const h = Math.max(1, Math.round((width / aspect) * dpr));
      canvas.width = w;
      canvas.height = h;
      const cellW = w / cols;
      const cellH = h / rows;
      const inverted = invert ?? backgroundLuminance(canvas) < 0.5;

      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = getComputedStyle(canvas).color || (inverted ? "#fff" : "#000");
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.font = monoFont(cellH);
      const mWidth = ctx.measureText("M").width || cellH * 0.6;
      ctx.font = monoFont((cellW / mWidth) * cellH);

      const maxLevel = levels - 1;
      const glyphs: string[] = [];
      const alphas: number[] = [];
      for (let level = 0; level <= maxLevel; level++) {
        const t = level / maxLevel;
        const n = inverted ? t : 1 - t;
        glyphs[level] = RAMP[Math.min(RAMP.length - 1, Math.round(n * (RAMP.length - 1)))] ?? RAMP[0] ?? ".";
        alphas[level] = 0.12 + 0.88 * n ** 0.85;
      }
      for (let r = 0; r < rows; r++) {
        const y = (r + 0.5) * cellH;
        for (let c = 0; c < cols; c++) {
          const level = Math.min(maxLevel, Math.max(0, cells.charCodeAt(r * cols + c) - 33));
          const glyph = glyphs[level];
          if (!glyph) continue;
          ctx.globalAlpha = alphas[level] ?? 1;
          ctx.fillText(glyph, (c + 0.5) * cellW, y);
        }
      }
      ctx.globalAlpha = 1;
      setDrawn(true);
    };
    document.fonts.ready.then(draw);
    return () => {
      cancelled = true;
    };
  }, [near, width, cells, levels, cols, rows, aspect, invert]);

  return (
    <div
      ref={wrapRef}
      role={label ? "img" : undefined}
      aria-label={label}
      className={cn("relative w-full transition-opacity duration-500 ease-out motion-reduce:transition-none", drawn ? "opacity-100" : "opacity-0", className)}
    >
      <canvas ref={canvasRef} aria-hidden="true" className="block size-full" />
    </div>
  );
}

"use client";

import { useEffect, useRef } from "react";
import { useLenis } from "lenis/react";
import { easeOutExpo } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/SmoothScroll";
import { usePrefersReducedMotion } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/hooks";

interface MinimapProps {
  /** aria-label of the overlay button. */
  label?: string;
  /** Hover tooltip under the box. */
  tooltip?: string;
}

/** Cap on text line bars painted per section (keeps the snapshot cheap on long pages). */
const MAX_TEXT_RECTS_PER_SECTION = 400;
/** Heading lines paint brighter; body text is a softer texture (sampled from the live canvas). */
const HEADING_SELECTOR = "h1, h2, h3, h4";
const TEXT_ALPHA = 0.45;
const HEADING_ALPHA = 0.7;
/** Media (screenshots, ASCII art, avatars) and filled panels are faint white boxes. */
const MEDIA_ALPHA = 0.16;
const PANEL_ALPHA = 0.07;

interface Clip {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

/** Intersection of every clipping ancestor (scroll areas, collapsed panels) below `stop`, or null. */
function clipRectOf(el: Element, stop: Element): Clip | null {
  let clip: Clip | null = null;
  for (let node = el.parentElement; node && node !== stop; node = node.parentElement) {
    const { overflowX, overflowY } = getComputedStyle(node);
    if (overflowX === "visible" && overflowY === "visible") continue;
    const r = node.getBoundingClientRect();
    clip = clip
      ? {
          left: Math.max(clip.left, r.left),
          top: Math.max(clip.top, r.top),
          right: Math.min(clip.right, r.right),
          bottom: Math.min(clip.bottom, r.bottom),
        }
      : { left: r.left, top: r.top, right: r.right, bottom: r.bottom };
  }
  return clip;
}

function isTransparent(color: string) {
  return color === "transparent" || /^rgba\(.*,\s*0\)$/.test(color) || /\/\s*0\)$/.test(color);
}

/**
 * Paints the live site's minimap wireframe into `canvas`: a transparent layer of translucent white
 * shapes (text lines as bars, media as boxes, filled panels as faint boxes) at the box-to-viewport
 * scale (54/900 = 0.06 on desktop), so the blurred `bg-black/50` box shows through. Returns the
 * page→minimap scale.
 */
function paintPage(canvas: HTMLCanvasElement, width: number, boxHeight: number) {
  const docEl = document.documentElement;
  const pageWidth = docEl.clientWidth || window.innerWidth;
  const pageHeight = docEl.scrollHeight;
  const scale = boxHeight / window.innerHeight;
  const height = Math.max(1, Math.ceil(pageHeight * scale));
  const dpr = Math.min(window.devicePixelRatio || 1, 2);

  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;

  const ctx = canvas.getContext("2d");
  if (!ctx) return scale;
  ctx.setTransform(dpr * scale, 0, 0, dpr * scale, 0, 0);
  ctx.clearRect(0, 0, pageWidth, pageHeight);
  ctx.fillStyle = "#fff";

  const scrollY = window.scrollY;
  const box = (rect: DOMRect, alpha: number) => {
    ctx.globalAlpha = alpha;
    ctx.fillRect(rect.left, rect.top + scrollY, rect.width, rect.height);
  };
  const range = document.createRange();
  const roots = [document.querySelector("main"), document.querySelector("footer")].filter(
    (el): el is HTMLElement => el !== null,
  );

  for (const root of roots) {
    for (const section of Array.from(root.children)) {
      if (!(section instanceof HTMLElement)) continue;
      const sectionStyle = getComputedStyle(section);
      if (sectionStyle.position === "fixed" || sectionStyle.display === "none") continue;

      // Media and filled panels (skip the section itself and full-bleed wrappers).
      for (const el of Array.from(section.querySelectorAll<HTMLElement>("img, canvas, svg, video, [class*='bg-']"))) {
        const rect = el.getBoundingClientRect();
        if (rect.width < 8 || rect.height < 8) continue;
        const tag = el.tagName;
        // WebGL scenes (spiral, glyph fields) and their wrapper panels are left out, as live.
        const sceneWidth = pageWidth * 0.46;
        const scene =
          tag === "CANVAS"
            ? rect.width > sceneWidth
            : Array.from(el.querySelectorAll("canvas")).some((c) => c.getBoundingClientRect().width > sceneWidth);
        if (scene) continue;
        if (tag === "IMG" || tag === "CANVAS" || tag === "VIDEO") {
          if (getComputedStyle(el).opacity === "0") continue;
          box(rect, MEDIA_ALPHA);
        } else if (tag !== "svg" && rect.width < pageWidth * 0.95) {
          const style = getComputedStyle(el);
          if (!isTransparent(style.backgroundColor) && style.position !== "fixed") box(rect, PANEL_ALPHA);
        }
      }

      // Text lines as bars spanning the line box's middle 60%.
      const walker = document.createTreeWalker(section, NodeFilter.SHOW_TEXT);
      let painted = 0;
      for (let node = walker.nextNode(); node && painted < MAX_TEXT_RECTS_PER_SECTION; node = walker.nextNode()) {
        const parent = node.parentElement;
        if (!parent || !node.textContent?.trim()) continue;
        const textStyle = getComputedStyle(parent);
        if (textStyle.visibility === "hidden" || parent.closest(".sr-only, [aria-hidden='true']")) continue;
        ctx.globalAlpha = parent.closest(HEADING_SELECTOR) ? HEADING_ALPHA : TEXT_ALPHA;
        const clip = clipRectOf(parent, section);
        range.selectNodeContents(node);
        for (const line of Array.from(range.getClientRects())) {
          if (line.width < 2 || line.height < 2) continue;
          let { left, top } = line;
          let right = line.right;
          let bottom = line.bottom;
          if (clip) {
            left = Math.max(left, clip.left);
            right = Math.min(right, clip.right);
            top = Math.max(top, clip.top);
            bottom = Math.min(bottom, clip.bottom);
            if (right - left < 1 || bottom - top < line.height * 0.5) continue;
          }
          ctx.fillRect(left, top + scrollY + (bottom - top) * 0.2, right - left, (bottom - top) * 0.6);
          if (++painted >= MAX_TEXT_RECTS_PER_SECTION) break;
        }
      }
    }
  }
  ctx.globalAlpha = 1;
  return scale;
}

/**
 * Fixed top-right page overview: a scroll-linked canvas thumbnail of the page plus the looping
 * accent scan (5s). Hovering shows the accent ring and "Inspect ↗"; clicking scrolls to the top.
 */
export function Minimap({ label, tooltip = "Inspect ↗" }: MinimapProps) {
  const boxRef = useRef<HTMLDivElement>(null);
  const baseLayerRef = useRef<HTMLDivElement>(null);
  const scanLayerRef = useRef<HTMLDivElement>(null);
  const baseCanvasRef = useRef<HTMLCanvasElement>(null);
  const scanCanvasRef = useRef<HTMLCanvasElement>(null);
  const lenis = useLenis();
  const reduced = usePrefersReducedMotion();

  useEffect(() => {
    const box = boxRef.current;
    const baseCanvas = baseCanvasRef.current;
    const scanCanvas = scanCanvasRef.current;
    const layers = [baseLayerRef.current, scanLayerRef.current].filter((el): el is HTMLDivElement => el !== null);
    if (!box || !baseCanvas || !scanCanvas) return;

    let scale = 0;
    let redrawTimer = 0;
    let cancelled = false;

    const applyScroll = () => {
      const transform = `translate3d(0, ${-(window.scrollY * scale)}px, 0)`;
      for (const layer of layers) layer.style.transform = transform;
    };

    const redraw = () => {
      if (cancelled) return;
      const width = box.clientWidth || 96;
      scale = paintPage(baseCanvas, width, box.clientHeight || 54);
      scanCanvas.width = baseCanvas.width;
      scanCanvas.height = baseCanvas.height;
      scanCanvas.style.width = baseCanvas.style.width;
      scanCanvas.style.height = baseCanvas.style.height;
      scanCanvas.getContext("2d")?.drawImage(baseCanvas, 0, 0);
      applyScroll();
    };

    const scheduleRedraw = () => {
      window.clearTimeout(redrawTimer);
      redrawTimer = window.setTimeout(redraw, 200);
    };

    redraw();
    void document.fonts?.ready.then(scheduleRedraw);

    window.addEventListener("scroll", applyScroll, { passive: true });
    window.addEventListener("resize", scheduleRedraw);
    const observer = new ResizeObserver(scheduleRedraw);
    const main = document.querySelector("main");
    if (main) observer.observe(main);
    observer.observe(box);

    return () => {
      cancelled = true;
      window.clearTimeout(redrawTimer);
      window.removeEventListener("scroll", applyScroll);
      window.removeEventListener("resize", scheduleRedraw);
      observer.disconnect();
    };
  }, []);

  const scrollToTop = () => {
    if (lenis) {
      lenis.scrollTo(0, reduced ? { immediate: true } : { duration: 1.2, easing: easeOutExpo });
      return;
    }
    window.scrollTo({ top: 0, behavior: reduced ? "auto" : "smooth" });
  };

  return (
    <div className="group fixed top-8 right-8 z-3 aspect-video h-44 lg:top-16 lg:right-16 lg:h-54">
      <div
        ref={boxRef}
        aria-hidden="true"
        className="pointer-events-none relative h-full w-full overflow-hidden rounded-[3px] bg-black/50 ring-1 ring-white/15 ring-inset backdrop-blur-sm"
      >
        <div className="absolute inset-0">
          <div ref={baseLayerRef} className="absolute top-0 left-0 will-change-transform">
            <canvas ref={baseCanvasRef} className="block" />
          </div>
        </div>
        <div className="absolute inset-0 animate-minimap-scan overflow-hidden motion-reduce:hidden">
          <div className="absolute inset-0 [mask-image:linear-gradient(to_top,black,transparent_60%)]">
            <div className="absolute inset-0 animate-minimap-scan-counter">
              <div ref={scanLayerRef} className="absolute top-0 left-0 will-change-transform">
                <canvas ref={scanCanvasRef} className="block" />
              </div>
            </div>
          </div>
          <div className="absolute inset-x-0 bottom-0 h-1/2 bg-linear-to-b from-transparent to-accent/20" />
          <div className="absolute inset-x-0 bottom-0 h-px bg-accent" />
          <div className="absolute -bottom-2 -left-2 size-4 rounded-full bg-accent" />
          <div className="absolute -right-2 -bottom-2 size-4 rounded-full bg-accent" />
        </div>
      </div>
      <button
        type="button"
        aria-label={label ?? "Page overview"}
        onClick={scrollToTop}
        className="absolute inset-0 cursor-pointer rounded-[3px] ring-inset transition-shadow hover:ring-2 hover:ring-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      />
      <span
        aria-hidden="true"
        className="pointer-events-none absolute top-full right-0 mt-4 hidden whitespace-nowrap rounded-2 bg-black px-6 py-3 font-mono text-ui text-white/70 uppercase leading-none tracking-wide ring-1 ring-white/15 group-hover:block"
      >
        {tooltip}
      </span>
    </div>
  );
}

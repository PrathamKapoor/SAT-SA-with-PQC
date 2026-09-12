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
const MAX_TEXT_RECTS_PER_SECTION = 160;
/** Heading lines paint near-opaque; other text is a faint texture. */
const HEADING_SELECTOR = "h1, h2, h3, h4";

function isTransparent(color: string) {
  return color === "transparent" || /^rgba\(.*,\s*0\)$/.test(color) || /\/\s*0\)$/.test(color);
}

/**
 * Paints a scaled wireframe snapshot of the page into `canvas` (`width` CSS px wide): the body
 * ground, each `main > *` section in its background colour, text lines as 1px bars in their text
 * colour, and whatever follows `<main>` (footer). Returns the page→minimap scale.
 */
function paintPage(canvas: HTMLCanvasElement, width: number) {
  const docEl = document.documentElement;
  const pageWidth = docEl.scrollWidth || window.innerWidth;
  const pageHeight = docEl.scrollHeight;
  const scale = width / pageWidth;
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
  ctx.fillStyle = getComputedStyle(document.body).backgroundColor;
  ctx.fillRect(0, 0, pageWidth, pageHeight);

  const main = document.querySelector("main");
  if (!main) return scale;
  const scrollY = window.scrollY;
  const mainRect = main.getBoundingClientRect();
  const mainStyle = getComputedStyle(main);
  if (!isTransparent(mainStyle.backgroundColor)) {
    ctx.fillStyle = mainStyle.backgroundColor;
    ctx.fillRect(mainRect.left, mainRect.top + scrollY, mainRect.width, mainRect.height);
  }

  const barHeight = 1 / scale;
  const range = document.createRange();

  for (const child of Array.from(main.children)) {
    if (!(child instanceof HTMLElement)) continue;
    const style = getComputedStyle(child);
    if (style.position === "fixed" || style.display === "none") continue;
    const rect = child.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) continue;
    if (!isTransparent(style.backgroundColor)) {
      ctx.fillStyle = style.backgroundColor;
      ctx.fillRect(rect.left, rect.top + scrollY, rect.width, rect.height);
    }

    // Text lines: walk text nodes only (element boxes would add spurious bars).
    const walker = document.createTreeWalker(child, NodeFilter.SHOW_TEXT);
    let painted = 0;
    for (let node = walker.nextNode(); node && painted < MAX_TEXT_RECTS_PER_SECTION; node = walker.nextNode()) {
      const parent = node.parentElement;
      if (!parent || !node.textContent?.trim()) continue;
      const textStyle = getComputedStyle(parent);
      if (textStyle.visibility === "hidden" || parent.closest("[aria-hidden='true']")) continue;
      ctx.globalAlpha = parent.closest(HEADING_SELECTOR) ? 0.9 : 0.4;
      ctx.fillStyle = textStyle.color;
      range.selectNodeContents(node);
      for (const line of Array.from(range.getClientRects())) {
        if (line.width < 2 || line.height < 2) continue;
        ctx.fillRect(line.left, line.top + scrollY + line.height / 2, line.width, barHeight);
        if (++painted >= MAX_TEXT_RECTS_PER_SECTION) break;
      }
    }
    ctx.globalAlpha = 1;
  }

  // Footer (and anything else after <main>): stacked below main in its own ground colour.
  let y = mainRect.bottom + scrollY;
  let sibling = main.nextElementSibling;
  while (sibling instanceof HTMLElement) {
    const own = getComputedStyle(sibling).backgroundColor;
    const first = sibling.firstElementChild;
    const color = !isTransparent(own) ? own : first ? getComputedStyle(first).backgroundColor : own;
    const h = sibling.offsetHeight;
    if (!isTransparent(color) && h > 0) {
      ctx.fillStyle = color;
      ctx.fillRect(0, y, pageWidth, h);
    }
    y += h;
    sibling = sibling.nextElementSibling;
  }

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
      scale = paintPage(baseCanvas, width);
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

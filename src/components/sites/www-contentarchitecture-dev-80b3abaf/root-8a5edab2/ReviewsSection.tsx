"use client";

import {
  useEffect,
  useId,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { cn } from "@/lib/utils";
import { AsciiImage, type AsciiGrid } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/AsciiImage";
import { DeferredMount } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/DeferredMount";
import { GlyphField } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/GlyphField";
import type { GlyphFieldModel } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/glyph-model";
import { Reveal } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Reveal";
import {
  useInView,
  useIsTouchDevice,
  usePrefersReducedMotion,
} from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/hooks";

export interface ReviewItem {
  /** Full quote, typed out when its slide becomes active (include the curly quotes). */
  quote: string;
  name: string;
  role: string;
  /** 32×18 ASCII grid shown by default; the real photo is revealed on hover (always on touch). */
  avatar: { ascii: AsciiGrid; src: string };
}

/** Screen-reader affordance labels. Templates use `{current}`, `{index}`, `{total}` and `{name}`. */
export interface ReviewsControlsCopy {
  previousLabel?: string;
  nextLabel?: string;
  /** Polite live-region text, e.g. "Slide {current} of {total}". */
  statusTemplate?: string;
  /** Per-slide aria-label, e.g. "{index} of {total}: {name}". */
  slideLabelTemplate?: string;
}

export interface ReviewsContent {
  /** Section anchor id. Defaults to "reviews". */
  id?: string;
  /** Carousel aria-label. */
  label: string;
  /** Slides, rendered in order (any count). */
  items: readonly ReviewItem[];
  /** Backdrop phrase field. */
  glyph: { model: GlyphFieldModel; phrase: string };
  controls?: ReviewsControlsCopy;
}

const DEFAULT_CONTROLS: Required<ReviewsControlsCopy> = {
  previousLabel: "Previous slide",
  nextLabel: "Next slide",
  statusTemplate: "Slide {current} of {total}",
  slideLabelTemplate: "{index} of {total}: {name}",
};

/** Typewriter speed (ms per character). */
const CHAR_MS = 22;
/** Release velocity (px/ms) is projected this far ahead when picking the slide to settle on. */
const MOMENTUM_MS = 120;
/** Fallback for browsers without `scrollend`: re-enable snapping after the settle scroll. */
const SETTLE_TIMEOUT_MS = 900;

const SLIDE_BASE = "min-w-0 shrink-0 grow-0 snap-center";
const SLIDE_ONLY = "basis-[calc(var(--carousel-slide)+var(--carousel-gutter)*2)] px-[var(--carousel-gutter)]";
const SLIDE_FIRST = "basis-[calc(var(--carousel-slide)+var(--carousel-gutter))] pl-[var(--carousel-gutter)]";
const SLIDE_MIDDLE = "basis-[var(--carousel-slide)]";
const SLIDE_LAST = "basis-[calc(var(--carousel-slide)+var(--carousel-gutter))] pr-[var(--carousel-gutter)]";

const FRAME_CLASS =
  "rounded-8 p-6 shadow-lg ring ring-black-deep transition-colors duration-300 lg:p-8 bg-black-deep bg-dither h-full";
const FIGURE_CLASS =
  "group flex h-full min-h-300 flex-col justify-between gap-24 overflow-hidden rounded-4 bg-black p-24 ring-1 ring-white/10 lg:min-h-460 lg:gap-48 lg:p-48";
const CURSOR_CLASS =
  "absolute top-[0.1em] left-0 inline-block h-[1.05em] w-[0.1em] animate-cursor-blink bg-current";
const IMAGE_CLASS =
  "max-w-full pointer-events-none absolute inset-0 size-full object-cover opacity-0 transition-opacity duration-500 ease-out group-hover:opacity-100 group-data-[active=true]:opacity-100 motion-reduce:transition-none";
const CONTROL_CLASS =
  "flex size-44 cursor-pointer items-center justify-center font-mono text-body-20 text-white/50 leading-none transition-colors hover:text-white disabled:pointer-events-none disabled:text-white/15";

const DIGITS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"] as const;

function fill(template: string, values: Record<string, string | number>) {
  return template.replace(/\{(\w+)\}/g, (match, key: string) => (key in values ? String(values[key]) : match));
}

function slideClass(index: number, count: number) {
  if (count === 1) return SLIDE_ONLY;
  if (index === 0) return SLIDE_FIRST;
  if (index === count - 1) return SLIDE_LAST;
  return SLIDE_MIDDLE;
}

/** scrollLeft that centres each slide (what `snap-center` resolves to), clamped to the scroll range. */
function snapTargets(track: HTMLElement) {
  const trackLeft = track.getBoundingClientRect().left + track.clientLeft;
  const max = Math.max(0, track.scrollWidth - track.clientWidth);
  return Array.from(track.children, (slide) => {
    const rect = slide.getBoundingClientRect();
    const centred = track.scrollLeft + rect.left - trackLeft + rect.width / 2 - track.clientWidth / 2;
    return Math.min(max, Math.max(0, centred));
  });
}

function nearestIndex(targets: readonly number[], position: number) {
  let best = 0;
  let bestDistance = Number.POSITIVE_INFINITY;
  targets.forEach((target, index) => {
    const distance = Math.abs(target - position);
    if (distance < bestDistance - 0.5) {
      best = index;
      bestDistance = distance;
    }
  });
  return best;
}

/**
 * Types `quote` once, the first time `trigger` is true, and then keeps it complete (the latch
 * survives the slide becoming inactive mid-typing). Reduced motion shows the full quote.
 */
function useQuoteTypewriter(length: number, trigger: boolean, reduced: boolean) {
  const [started, setStarted] = useState(false);
  const [chars, setChars] = useState(0);
  // Latch during render (React's "adjust state on prop change" pattern), so the effect below only
  // restarts on unmount/remount and never stops half-way when the slide loses focus.
  if (trigger && !started) setStarted(true);

  useEffect(() => {
    if (!started || reduced) return;
    let frame = 0;
    let startTime = -1;
    const tick = (now: number) => {
      if (startTime < 0) startTime = now;
      const visible = Math.min(length, Math.floor((now - startTime) / CHAR_MS));
      setChars(visible);
      if (visible < length) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [started, reduced, length]);

  return reduced ? length : chars;
}

interface ReviewCardProps {
  item: ReviewItem;
  /** Start typing (slide active and carousel in view). */
  trigger: boolean;
  reduced: boolean;
  /** Touch devices always show the photo (no hover). */
  touch: boolean;
}

function ReviewCard({ item, trigger, reduced, touch }: ReviewCardProps) {
  const glyphs = Array.from(item.quote);
  const visible = useQuoteTypewriter(glyphs.length, trigger, reduced);
  const typed = glyphs.slice(0, visible).join("");
  const rest = glyphs.slice(visible).join("");

  return (
    <div className={FRAME_CLASS}>
      <figure className={FIGURE_CLASS} data-active={touch}>
        <div>
          <blockquote>
            <div className="text-body-30 text-white lg:text-headline-10">
              <span className="sr-only">{item.quote}</span>
              <span aria-hidden="true" className="whitespace-pre-wrap">
                {typed}
                <span className="relative inline">
                  <span className={CURSOR_CLASS} />
                </span>
                <span className="text-transparent">{rest}</span>
              </span>
            </div>
          </blockquote>
        </div>
        <figcaption className="flex items-center gap-16">
          <div className="relative size-48 shrink-0 overflow-hidden rounded-full ring-1 ring-white/15">
            <AsciiImage {...item.avatar.ascii} className="absolute inset-0" />
            {/* eslint-disable-next-line @next/next/no-img-element -- lazy photo layer, sized by its container */}
            <img
              loading="lazy"
              decoding="async"
              alt=""
              src={item.avatar.src}
              sizes="48px"
              aria-hidden="true"
              className={IMAGE_CLASS}
            />
          </div>
          <div className="min-w-0 flex-1 font-mono text-caption-10 uppercase">
            <p className="truncate text-white">
              <Reveal as="span" className="inline-block">
                {item.name}
              </Reveal>
            </p>
            <p className="truncate text-dark-grey">
              <Reveal as="span" className="inline-block">
                {item.role}
              </Reveal>
            </p>
          </div>
        </figcaption>
      </figure>
    </div>
  );
}

/** One odometer column: 0–9 stacked, translated up by `digit` em. */
function DigitRoller({ digit }: { digit: number }) {
  return (
    <span className="relative inline-block h-[1em] overflow-hidden align-baseline leading-[1em]">
      <span className="invisible">{digit}</span>
      <span
        className="absolute inset-x-0 top-0 flex flex-col motion-safe:transition-transform motion-safe:duration-500 motion-safe:ease-[cubic-bezier(0.23,1,0.32,1)]"
        style={{ transform: digit === 0 ? "none" : `translateY(-${digit}em)` }}
      >
        {DIGITS.map((glyph, index) => (
          <span key={glyph} className="block h-[1em] leading-[1em]" aria-hidden={index === digit ? undefined : true}>
            {glyph}
          </span>
        ))}
      </span>
    </span>
  );
}

interface DragState {
  pointerId: number;
  startX: number;
  startScroll: number;
  lastX: number;
  lastTime: number;
  /** Smoothed pointer velocity, px/ms (positive = moving right). */
  velocity: number;
}

/**
 * Testimonials: a scroll-snap carousel (native wheel/touch scrolling, mouse drag, prev/next
 * buttons with an odometer counter) over a phrase-field backdrop. The active slide (the one whose
 * snap position is nearest the scroll position) types its quote once.
 */
export function ReviewsSection({ content }: { content: ReviewsContent }) {
  const { id = "reviews", label, items, glyph } = content;
  const controls = { ...DEFAULT_CONTROLS, ...content.controls };
  const count = items.length;

  const trackId = useId();
  const trackRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<DragState | null>(null);
  const settleCleanupRef = useRef<(() => void) | null>(null);

  const [active, setActive] = useState(0);
  const reduced = usePrefersReducedMotion();
  const touch = useIsTouchDevice();
  const inView = useInView(trackRef, { threshold: 0.3 });

  // Active slide follows the scroll position (rAF-throttled), and re-evaluates on resize.
  useEffect(() => {
    const track = trackRef.current;
    if (!track) return;
    let frame = 0;
    const update = () => {
      frame = 0;
      setActive(nearestIndex(snapTargets(track), track.scrollLeft));
    };
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    track.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    return () => {
      track.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);

  // Drop any pending snap restore on unmount.
  useEffect(() => () => settleCleanupRef.current?.(), []);

  const scrollToIndex = (index: number) => {
    const track = trackRef.current;
    if (!track) return;
    const target = snapTargets(track)[index];
    if (target === undefined) return;
    track.scrollTo({ left: target, behavior: reduced ? "auto" : "smooth" });
  };

  const cancelSettle = () => {
    settleCleanupRef.current?.();
    settleCleanupRef.current = null;
  };

  /** Smooth-scroll to `left` with snapping off, then hand control back to CSS snapping. */
  const settle = (track: HTMLDivElement, left: number) => {
    const restore = () => {
      cancelSettle();
      track.style.scrollSnapType = "";
    };
    const onScrollEnd = () => {
      if (Math.abs(track.scrollLeft - left) < 2) restore();
    };
    const timer = window.setTimeout(restore, SETTLE_TIMEOUT_MS);
    track.addEventListener("scrollend", onScrollEnd);
    settleCleanupRef.current = () => {
      window.clearTimeout(timer);
      track.removeEventListener("scrollend", onScrollEnd);
    };
    track.scrollTo({ left, behavior: reduced ? "auto" : "smooth" });
  };

  // Mouse drag-to-scroll (blossom-carousel behaviour). Touch and pen keep native scrolling.
  const onPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.pointerType !== "mouse" || event.button !== 0) return;
    const track = event.currentTarget;
    cancelSettle();
    track.setPointerCapture(event.pointerId);
    track.style.scrollSnapType = "none";
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startScroll: track.scrollLeft,
      lastX: event.clientX,
      lastTime: event.timeStamp,
      velocity: 0,
    };
  };

  const onPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (!drag || event.pointerId !== drag.pointerId) return;
    event.currentTarget.scrollLeft = drag.startScroll - (event.clientX - drag.startX);
    const dt = event.timeStamp - drag.lastTime;
    if (dt > 0) drag.velocity = 0.8 * ((event.clientX - drag.lastX) / dt) + 0.2 * drag.velocity;
    drag.lastX = event.clientX;
    drag.lastTime = event.timeStamp;
  };

  const onPointerEnd = (event: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (!drag || event.pointerId !== drag.pointerId) return;
    dragRef.current = null;
    const track = event.currentTarget;
    if (track.hasPointerCapture(event.pointerId)) track.releasePointerCapture(event.pointerId);
    // A pointer held still before release carries no momentum.
    const velocity = event.timeStamp - drag.lastTime > 80 ? 0 : drag.velocity;
    const targets = snapTargets(track);
    const target = targets[nearestIndex(targets, track.scrollLeft - velocity * MOMENTUM_MS)];
    if (target === undefined) {
      track.style.scrollSnapType = "";
      return;
    }
    settle(track, target);
  };

  // Stops text selection and native image drag from hijacking a mouse drag.
  const onMouseDown = (event: ReactMouseEvent<HTMLDivElement>) => {
    if (event.button === 0) event.preventDefault();
  };

  const padLength = Math.max(2, String(count).length);
  const current = String(Math.min(active, Math.max(0, count - 1)) + 1).padStart(padLength, "0");
  const total = String(count).padStart(padLength, "0");

  return (
    <div
      id={id}
      data-page-builder-section="testimonialsSection"
      className="relative isolate overflow-x-clip bg-black py-72 text-white lg:pb-160"
    >
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-1 bg-black">
        <DeferredMount releaseMargin="100%">
          <GlyphField
            model={glyph.model}
            phrase={glyph.phrase}
            backgroundOnly
            interactive={false}
            entrance={false}
            maxFps={30}
          />
        </DeferredMount>
        <div aria-hidden="true" className="absolute inset-0 bg-black-deep/30" />
      </div>
      <div
        role="group"
        aria-roledescription="carousel"
        aria-label={label}
        className="[--carousel-gutter:--spacing(16)] [--carousel-slide:90%] md:[--carousel-slide:55%] lg:[--carousel-gutter:--spacing(80)]"
      >
        <div
          ref={trackRef}
          id={trackId}
          data-lenis-prevent-horizontal
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerEnd}
          onPointerCancel={onPointerEnd}
          onMouseDown={onMouseDown}
          className="flex snap-x snap-mandatory items-stretch gap-6 overflow-x-auto overflow-y-hidden overscroll-x-contain [scrollbar-width:none] motion-reduce:scroll-auto lg:gap-16 [&::-webkit-scrollbar]:hidden"
        >
          {items.map((item, index) => (
            <div
              key={`${item.name}-${index}`}
              role="group"
              aria-roledescription="slide"
              aria-label={fill(controls.slideLabelTemplate, { index: index + 1, total: count, name: item.name })}
              className={cn(SLIDE_BASE, slideClass(index, count))}
            >
              <ReviewCard item={item} trigger={inView && index === active} reduced={reduced} touch={touch} />
            </div>
          ))}
        </div>
        <div className="mt-48 flex items-center justify-center gap-16 lg:mt-64">
          <button
            type="button"
            aria-label={controls.previousLabel}
            aria-controls={trackId}
            disabled={active <= 0}
            onClick={() => scrollToIndex(active - 1)}
            className={CONTROL_CLASS}
          >
            <span aria-hidden="true">[&lt;]</span>
          </button>
          <p className="min-w-56 text-center font-mono text-caption-10 text-ghost-grey tabular-nums">
            <span className="inline-flex text-white">
              <span className="sr-only">{current}</span>
              <span aria-hidden="true" className="flex items-center">
                {Array.from(current, (char, index) => (
                  <DigitRoller key={index} digit={Number(char)} />
                ))}
              </span>
            </span>
            <span className="px-4 text-white/30">/</span>
            {total}
          </p>
          <button
            type="button"
            aria-label={controls.nextLabel}
            aria-controls={trackId}
            disabled={active >= count - 1}
            onClick={() => scrollToIndex(active + 1)}
            className={CONTROL_CLASS}
          >
            <span aria-hidden="true">[&gt;]</span>
          </button>
        </div>
        <p aria-live="polite" className="sr-only">
          {fill(controls.statusTemplate, { current: active + 1, total: count })}
        </p>
      </div>
    </div>
  );
}

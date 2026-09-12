"use client";

import React, { useCallback, useEffect, useId, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { gsap } from 'gsap';

import './MaskedHeading.css';

const clamp = (v: number, a: number, b: number) => (v < a ? a : v > b ? b : v);

const subscribeMotion = (callback: () => void) => {
  if (typeof window === 'undefined') return () => {};
  const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
  mq.addEventListener('change', callback);
  return () => mq.removeEventListener('change', callback);
};

const getMotionSnapshot = () => {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
};

const getMotionServerSnapshot = () => false;

export interface MaskedHeadingProps extends React.HTMLAttributes<HTMLElement> {
  text?: string;
  tag?: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6' | 'span' | 'div';
  mediaType?: 'image' | 'video';
  src?: string;
  poster?: string;
  fillScale?: number;
  parallax?: number;
  drift?: number;
  brightness?: number;
  saturation?: number;
  grayscale?: boolean;
  reveal?: 'rise' | 'wipe' | 'fade' | 'none';
  duration?: number;
  stagger?: number;
  trigger?: 'view' | 'mount' | 'hover';
  align?: 'left' | 'center' | 'right';
  weight?: number;
  tracking?: number;
  lineHeight?: number;
  textScale?: number;
  className?: string;
  style?: React.CSSProperties;
}

const MaskedHeading: React.FC<MaskedHeadingProps> = ({
  text = 'Supervision, backed by evidence.',
  tag = 'h1',
  mediaType = 'image',
  src = '',
  poster = '',
  fillScale = 1.12,
  parallax = 8,
  drift = 4,
  brightness = 1.05,
  saturation = 0.78,
  grayscale = false,
  reveal = 'rise',
  duration = 0.8,
  stagger = 0.055,
  trigger = 'view',
  align = 'left',
  weight = 700,
  tracking = -0.035,
  lineHeight = 0.98,
  textScale = 0.09,
  className = '',
  style,
  ...rest
}) => {
  const rootRef = useRef<HTMLElement | null>(null);
  const measureRef = useRef<HTMLSpanElement | null>(null);
  const revealRef = useRef<HTMLSpanElement | null>(null);
  const mediaRef = useRef<HTMLSpanElement | null>(null);
  const wordRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const baseRefs = useRef<(HTMLElement | null)[]>([]);
  const glyphRefs = useRef<(SVGTextElement | null)[]>([]);
  const offsetRef = useRef({ x: 0, y: 0, tx: 0, ty: 0 });

  const [hasError, setHasError] = useState(false);
  const reducedMotion = useSyncExternalStore(
    subscribeMotion,
    getMotionSnapshot,
    getMotionServerSnapshot
  );

  const rawId = useId();
  const clipId = `mh-${rawId.replace(/[^a-zA-Z0-9_-]/g, '')}`;
  const words = useMemo(() => String(text).split(/\s+/).filter(Boolean), [text]);

  const settingsRef = useRef({ fillScale, parallax, drift, brightness, saturation, grayscale, textScale });
  useEffect(() => {
    // Disable or reduce parallax on touch devices or reduced motion
    const isCoarse = typeof window !== 'undefined' && window.matchMedia('(pointer: coarse)').matches;
    const effParallax = reducedMotion ? 0 : isCoarse ? Math.min(2, parallax) : parallax;
    const effDrift = reducedMotion ? 0 : drift;

    settingsRef.current = {
      fillScale,
      parallax: effParallax,
      drift: effDrift,
      brightness,
      saturation,
      grayscale,
      textScale,
    };
  }, [fillScale, parallax, drift, brightness, saturation, grayscale, textScale, reducedMotion]);

  const place = useCallback(() => {
    const root = rootRef.current;
    const media = mediaRef.current;
    if (!root || !media) return;
    const s = settingsRef.current;
    const W = root.clientWidth;
    const H = root.clientHeight;
    const off = offsetRef.current;

    const maxX = Math.max(0, ((s.fillScale - 1) / 2) * W);
    const maxY = Math.max(0, ((s.fillScale - 1) / 2) * H);

    media.style.transform = `translate3d(${clamp(off.x, -maxX, maxX).toFixed(2)}px, ${clamp(off.y, -maxY, maxY).toFixed(2)}px, 0) scale(${s.fillScale})`;
    media.style.filter = `brightness(${s.brightness}) saturate(${s.saturation})${s.grayscale ? ' grayscale(1)' : ''}`;
  }, []);

  const sync = useCallback(() => {
    const root = rootRef.current;
    const measure = measureRef.current;
    if (!root || !measure) return;
    const s = settingsRef.current;

    const W = root.clientWidth;
    const fs = clamp(W * s.textScale, 32, 84);
    measure.style.fontSize = `${fs}px`;

    const gEls = glyphRefs.current;
    for (let i = 0; i < words.length; i++) {
      const wEl = wordRefs.current[i];
      const bEl = baseRefs.current[i];
      const gEl = gEls[i];
      if (!wEl || !bEl || !gEl) continue;

      const rW = root.getBoundingClientRect();
      const rWord = wEl.getBoundingClientRect();
      const rBase = bEl.getBoundingClientRect();

      const x = rWord.left - rW.left;
      const y = rBase.top - rW.top;

      gEl.setAttribute('x', x.toFixed(2));
      gEl.setAttribute('y', y.toFixed(2));
      gEl.setAttribute('font-size', `${fs}px`);
    }

    place();
  }, [words, place]);

  useEffect(() => {
    sync();
    const ro = new ResizeObserver(sync);
    if (rootRef.current) ro.observe(rootRef.current);
    return () => ro.disconnect();
  }, [sync]);

  // Parallax pointer tracking
  useEffect(() => {
    if (reducedMotion) return;
    const root = rootRef.current;
    if (!root) return;

    const onMove = (e: PointerEvent) => {
      const s = settingsRef.current;
      if (s.parallax === 0) return;
      const rect = root.getBoundingClientRect();
      const normX = ((e.clientX - rect.left) / rect.width - 0.5) * 2;
      const normY = ((e.clientY - rect.top) / rect.height - 0.5) * 2;
      offsetRef.current.tx = normX * s.parallax;
      offsetRef.current.ty = normY * s.parallax;
    };

    const onLeave = () => {
      offsetRef.current.tx = 0;
      offsetRef.current.ty = 0;
    };

    root.addEventListener('pointermove', onMove);
    root.addEventListener('pointerleave', onLeave);

    let rafId: number;
    const loop = () => {
      const off = offsetRef.current;
      off.x += (off.tx - off.x) * 0.1;
      off.y += (off.ty - off.y) * 0.1;
      place();
      rafId = requestAnimationFrame(loop);
    };
    rafId = requestAnimationFrame(loop);

    return () => {
      root.removeEventListener('pointermove', onMove);
      root.removeEventListener('pointerleave', onLeave);
      cancelAnimationFrame(rafId);
    };
  }, [place, reducedMotion]);

  // Reveal Animation with reduced-motion check
  useEffect(() => {
    const root = rootRef.current;
    const glyphs = glyphRefs.current.filter(Boolean);
    if (!root || !glyphs.length) return;

    if (reducedMotion || reveal === 'none') {
      gsap.set(glyphs, { opacity: 1, y: 0, x: 0 });
      return;
    }

    const play = () => {
      if (reveal === 'rise') {
        gsap.fromTo(
          glyphs,
          { opacity: 0, y: 24 },
          {
            opacity: 1,
            y: 0,
            duration,
            stagger,
            ease: 'power3.out',
          }
        );
      } else if (reveal === 'fade') {
        gsap.fromTo(
          glyphs,
          { opacity: 0 },
          {
            opacity: 1,
            duration,
            stagger,
            ease: 'power2.out',
          }
        );
      } else {
        gsap.set(glyphs, { opacity: 1, y: 0 });
      }
    };

    if (trigger === 'view') {
      const io = new IntersectionObserver(
        (entries) => {
          if (entries.some((e) => e.isIntersecting)) {
            play();
            io.disconnect();
          }
        },
        { threshold: 0.15 }
      );
      io.observe(root);
      return () => io.disconnect();
    }

    play();
  }, [reveal, trigger, duration, stagger, reducedMotion]);

  const Tag = (tag || 'h1') as React.ElementType;

  return (
    <Tag
      ref={rootRef}
      className={`masked-heading ${className}`.trim()}
      style={{
        textAlign: align,
        fontWeight: weight,
        letterSpacing: `${tracking}em`,
        lineHeight,
        ...style,
      }}
      {...rest}
    >
      {/* Accessible visually-hidden text for screen readers */}
      <span className="sr-only">{text}</span>

      {/* Visible fallback if media fails or if reduced-motion is requested */}
      {hasError ? (
        <span className="text-white font-bold tracking-tight block">
          {text}
        </span>
      ) : (
        <>
          <span ref={measureRef} className="masked-heading__measure" aria-hidden="true">
            {words.map((word, i) => (
              <span
                key={`${word}-${i}`}
                ref={(el) => {
                  wordRefs.current[i] = el;
                }}
                className="masked-heading__word"
              >
                {word}
                <i
                  ref={(el) => {
                    baseRefs.current[i] = el;
                  }}
                  className="masked-heading__baseline"
                />
              </span>
            ))}
          </span>

          <svg className="masked-heading__defs" aria-hidden="true" focusable="false">
            <defs>
              <clipPath id={clipId} clipPathUnits="userSpaceOnUse">
                {words.map((word, i) => (
                  <text
                    key={`${word}-${i}`}
                    ref={(el) => {
                      glyphRefs.current[i] = el;
                    }}
                  >
                    {word}
                  </text>
                ))}
              </clipPath>
            </defs>
          </svg>

          <span ref={revealRef} className="masked-heading__reveal" aria-hidden="true">
            <span className="masked-heading__clip" style={{ clipPath: `url(#${clipId})` }}>
              <span ref={mediaRef} className="masked-heading__media">
                {mediaType === 'video' ? (
                  <video
                    className="masked-heading__source"
                    src={src}
                    poster={poster}
                    autoPlay
                    muted
                    loop
                    playsInline
                    onError={() => setHasError(true)}
                  />
                ) : (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    className="masked-heading__source"
                    src={src}
                    alt=""
                    draggable={false}
                    onError={() => setHasError(true)}
                  />
                )}
              </span>
            </span>
          </span>
        </>
      )}
    </Tag>
  );
};

export default MaskedHeading;

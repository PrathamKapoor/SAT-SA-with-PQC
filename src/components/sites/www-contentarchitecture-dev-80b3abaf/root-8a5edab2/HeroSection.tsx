"use client";

import { useMemo, useRef } from "react";
import { useLenis } from "lenis/react";
import { CaButton, type CaButtonVariant } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/CaButton";
import { Reveal } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Reveal";
import { SpiralScene } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/SpiralScene";
import { easeOutExpo } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/SmoothScroll";
import {
  useInView,
  usePrefersReducedMotion,
  useTypewriter,
} from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/hooks";

export interface HeroCta {
  /** First pill ("GET"). */
  leftText?: string;
  /** Second pill ("ACCESS"), joined to the first by the connector. */
  rightText?: string;
  href: string;
  /** Orange pulse dot in the top-right corner. */
  pulse?: boolean;
  /** Open in a new tab. */
  external?: boolean;
  /** Defaults to "dark". */
  variant?: CaButtonVariant;
}

export interface HeroContent {
  /** Mono uppercase line above the title. */
  eyebrow?: string;
  /** Headline; "\n" forces a line break (rendered with `whitespace-pre-line`). */
  title: string;
  /** Body paragraphs, one entry per paragraph. */
  body: readonly string[];
  cta?: HeroCta;
  /** lg-only status grid: rows of items, typed in reading order. Omit or leave empty to hide it. */
  statusRows?: readonly (readonly string[])[];
  /** Screen-reader text for the status grid. Defaults to each row joined by " ", rows joined by ". ". */
  statusLabel?: string;
  /** Text laid along the spiral rings; a "." renders as a dot. */
  spiralPhrase: string;
  /** aria-label of the lg scroll cue button. */
  scrollCueLabel: string;
}

const ZERO_WIDTH_SPACE = "​";

function HeroStatusGrid({ rows, label }: { rows: readonly (readonly string[])[]; label?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref);
  const items = useMemo(() => rows.flat(), [rows]);
  /** Index of each row's first item within `items`. */
  const rowOffsets = useMemo(() => rows.map((_, r) => rows.slice(0, r).reduce((sum, row) => sum + row.length, 0)), [rows]);
  const { visibleChars, activeRow, done } = useTypewriter(items, {
    charDelay: 30,
    lineDelay: 60,
    startDelay: 600,
    enabled: inView,
  });
  const cursorIndex = done ? items.length - 1 : activeRow;
  const srLabel = label ?? rows.map((row) => row.join(" ")).join(". ");

  return (
    <div className="hidden lg:block">
      <div ref={ref} className="font-mono text-caption-10 uppercase">
        <span className="sr-only">{srLabel}</span>
        <div aria-hidden="true" className="flex flex-col gap-y-4">
          {rows.map((row, rowIndex) => (
            <div key={rowIndex} className="flex flex-wrap items-baseline justify-between gap-x-16 gap-y-4">
              {row.map((text, i) => {
                const index = (rowOffsets[rowIndex] ?? 0) + i;
                const typed = text.slice(0, visibleChars[index] ?? 0);
                return (
                  <span key={i} className="relative inline-block whitespace-pre">
                    <span className="invisible">{text}</span>
                    <span className="absolute inset-y-0 left-0 whitespace-pre">
                      <span className="relative inline-block">
                        {ZERO_WIDTH_SPACE}
                        {typed}
                        {index === cursorIndex ? (
                          <span
                            aria-hidden="true"
                            className="absolute top-0 left-full ml-px h-[1em] w-[0.55em] translate-y-[0.15em] animate-cursor-blink bg-current"
                          />
                        ) : null}
                      </span>
                    </span>
                  </span>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function HeroScrollCue({ label }: { label: string }) {
  const lenis = useLenis();
  const reduced = usePrefersReducedMotion();

  const handleClick = () => {
    if (lenis) {
      lenis.scrollTo(
        lenis.scroll + window.innerHeight,
        reduced ? { immediate: true } : { duration: 1.2, easing: easeOutExpo },
      );
      return;
    }
    window.scrollBy({ top: window.innerHeight, behavior: reduced ? "auto" : "smooth" });
  };

  return (
    <button
      type="button"
      aria-label={label}
      onClick={handleClick}
      className="group cursor-pointer flex-col items-center rounded-4 bg-black-deep px-8 py-10 ring-1 ring-white/20 ring-inset transition-shadow hover:ring-white/40 focus-visible:ring-2 focus-visible:ring-white/60 absolute bottom-40 left-[calc(50%_+_8px)] hidden -translate-x-1/2 lg:flex motion-safe:animate-fade-in"
      style={{ animationDelay: "400ms", animationFillMode: "both" }}
    >
      <span
        aria-hidden="true"
        className="relative block h-48 w-6 overflow-hidden"
        style={{
          backgroundImage: "repeating-linear-gradient(to bottom, rgba(255,255,255,0.12) 0 1px, transparent 1px 8px)",
        }}
      >
        <span className="absolute inset-x-0 top-0 h-6 animate-hero-scroll-cue bg-white/90 transition-colors group-hover:bg-white motion-reduce:hidden" />
        <span className="absolute inset-x-0 bottom-0 hidden h-6 bg-white/90 motion-reduce:block" />
      </span>
    </button>
  );
}

/**
 * Hero: text column (eyebrow, title, body, split CTA, typed status grid) beside the SpiralScene
 * panel. Mobile stacks the text above an 80vh spiral row; lg splits 5/12 text and 6/12 spiral.
 */
export function HeroSection({ content }: { content: HeroContent }) {
  const { eyebrow, title, body, cta, statusRows, statusLabel, spiralPhrase, scrollCueLabel } = content;

  return (
    <div
      data-page-builder-section="mainHeroSection"
      className="relative grid min-h-svh grid-cols-1 grid-rows-[auto_80vh] gap-x-16 bg-off-white text-black lg:grid-cols-12 lg:grid-rows-1"
    >
      <div className="flex flex-col gap-48 px-16 pt-160 pb-48 lg:col-span-5 lg:justify-center lg:pt-64 lg:pr-0 lg:pl-80">
        <div className="my-auto">
          {eyebrow ? (
            <p className="mb-20 font-mono text-caption-20 uppercase">
              <Reveal as="span" className="inline-block">
                {eyebrow}
              </Reveal>
            </p>
          ) : null}
          <h1 className="mb-32 whitespace-pre-line text-balance font-medium text-headline-20">
            <Reveal as="span" className="inline-block">
              {title}
            </Reveal>
          </h1>
          {body.length > 0 ? (
            <div className="w-full text-body-20 text-dark-grey">
              <div className="flex w-full flex-col gap-[1em] [&_[data-text]>*:not(:first-child)]:indent-0">
                {body.map((paragraph, i) => (
                  <Reveal key={i} className="empty:h-[1lh]">
                    {paragraph}
                  </Reveal>
                ))}
              </div>
            </div>
          ) : null}
          {cta ? (
            <div className="block w-full mt-32">
              <Reveal rise delay={300}>
                <CaButton
                  leftText={cta.leftText}
                  rightText={cta.rightText}
                  variant={cta.variant ?? "dark"}
                  showPulseDot={cta.pulse}
                  href={cta.href}
                  external={cta.external}
                />
              </Reveal>
            </div>
          ) : null}
        </div>
        {statusRows && statusRows.length > 0 ? <HeroStatusGrid rows={statusRows} label={statusLabel} /> : null}
      </div>
      <div className="relative overflow-hidden bg-black lg:col-span-6 lg:col-start-7 lg:aspect-auto">
        <div className="size-full absolute inset-0">
          <SpiralScene phrase={spiralPhrase} />
        </div>
      </div>
      <HeroScrollCue label={scrollCueLabel} />
    </div>
  );
}

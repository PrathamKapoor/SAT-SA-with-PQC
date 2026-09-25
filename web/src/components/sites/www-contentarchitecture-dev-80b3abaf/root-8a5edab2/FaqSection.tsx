"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { CaButton, type CaButtonVariant } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/CaButton";
import { DeferredMount } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/DeferredMount";
import { GlyphField } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/GlyphField";
import type { GlyphFieldModel } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/glyph-model";
import { Reveal } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Reveal";
import { usePrefersReducedMotion } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/hooks";

/** Inline link inside an answer paragraph (rendered dashed-underlined). */
export interface FaqLink {
  text: string;
  href: string;
  /** Open in a new tab (`target="_blank" rel="noopener noreferrer"`). */
  external?: boolean;
}

/** A run of an answer paragraph: plain text or an inline link. */
export type FaqInline = string | FaqLink;

/** One answer paragraph: plain text, or a sequence of text runs and links. */
export type FaqParagraph = string | readonly FaqInline[];

export interface FaqItem {
  question: string;
  /** One entry per paragraph. */
  answer: readonly FaqParagraph[];
}

export interface FaqCta {
  /** First pill ("GET"). */
  leftText?: string;
  /** Second pill ("ACCESS"), joined to the first by the connector. */
  rightText?: string;
  href: string;
  /** Orange pulse dot in the top-right corner. */
  pulse?: boolean;
  /** Open in a new tab. */
  external?: boolean;
  /** Defaults to "light". */
  variant?: CaButtonVariant;
}

export interface FaqGlyph {
  model: GlyphFieldModel;
  /** Uppercase phrase tiled across the background-only glyph field. */
  phrase: string;
}

export interface FaqContent {
  /** Section anchor id. Defaults to "faq". */
  id?: string;
  /** Sticky left-column heading. */
  title: string;
  /** Split pill pinned to the bottom of the sticky column on lg (last on mobile). */
  cta?: FaqCta;
  /** Questions in display order; numbering (`Q.001`) is automatic. */
  items: readonly FaqItem[];
  /** Prefix before the zero-padded number. Defaults to "Q.". */
  numberPrefix?: string;
  /** Index of the item open on load. Defaults to 0; `null` starts all closed. */
  defaultOpenIndex?: number | null;
  /** Background-only GlyphField backdrop. Omit for a plain #232323 backdrop. */
  glyph?: FaqGlyph;
}

const EASE = "cubic-bezier(0.23, 1, 0.32, 1)";
const DURATION = 350;

const LINK_CLASS = "underline decoration-from-font decoration-dashed underline-offset-3";

function renderInline(run: FaqInline, key: number): ReactNode {
  if (typeof run === "string") return run;
  return (
    <a
      key={key}
      className={LINK_CLASS}
      href={run.href}
      {...(run.external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
    >
      {run.text}
    </a>
  );
}

function renderParagraph(paragraph: FaqParagraph): ReactNode {
  if (typeof paragraph === "string") return paragraph;
  return paragraph.map((run, i) => renderInline(run, i));
}

/**
 * Answer panel: measured-height collapse. Opening grows 0 → content height (then releases to
 * `auto`) while fading in; closing collapses to 0 and the fade finishes as the height lands.
 */
function FaqPanel({
  id,
  labelledBy,
  open,
  children,
}: {
  id: string;
  labelledBy: string;
  open: boolean;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const reduced = usePrefersReducedMotion();
  const prevOpen = useRef(open);
  // Initial style only: after mount the effect below owns height/opacity imperatively.
  const [initialStyle] = useState(() => (open ? { height: "auto", opacity: 1 } : { height: "0px", opacity: 0 }));

  useEffect(() => {
    const el = ref.current;
    if (!el || prevOpen.current === open) return;
    prevOpen.current = open;

    if (reduced) {
      el.style.transition = "none";
      el.style.height = open ? "auto" : "0px";
      el.style.opacity = open ? "1" : "0";
      return;
    }

    // Start from the current rendered height so interrupted toggles reverse smoothly.
    const from = el.getBoundingClientRect().height;
    const to = open ? el.scrollHeight : 0;
    el.style.transition = "none";
    el.style.height = `${from}px`;
    void el.offsetHeight;

    if (from === to) {
      el.style.height = open ? "auto" : "0px";
      el.style.opacity = open ? "1" : "0";
      return;
    }

    el.style.transition = open
      ? `height ${DURATION}ms ${EASE}, opacity ${DURATION}ms ${EASE}`
      : `height ${DURATION}ms ${EASE}, opacity 150ms linear 200ms`;
    el.style.height = `${to}px`;
    el.style.opacity = open ? "1" : "0";

    const handleEnd = (event: TransitionEvent) => {
      if (event.target !== el || event.propertyName !== "height") return;
      if (open) {
        el.style.transition = "none";
        el.style.height = "auto";
      }
    };
    el.addEventListener("transitionend", handleEnd);
    return () => el.removeEventListener("transitionend", handleEnd);
  }, [open, reduced]);

  return (
    <div ref={ref} id={id} role="region" aria-labelledby={labelledBy} inert={!open} className="overflow-hidden" style={initialStyle}>
      {children}
    </div>
  );
}

function FaqRow({
  item,
  label,
  open,
  onToggle,
}: {
  item: FaqItem;
  label: string;
  open: boolean;
  onToggle: () => void;
}) {
  const baseId = useId();
  const buttonId = `${baseId}button`;
  const panelId = `${baseId}panel`;

  return (
    <li className="border-white/15 border-b">
      <h3>
        <button
          type="button"
          id={buttonId}
          aria-expanded={open}
          aria-controls={panelId}
          onClick={onToggle}
          className="group flex w-full cursor-pointer items-center justify-between gap-24 py-24 text-left font-mono text-caption-20 uppercase"
        >
          <span>
            <span className="text-dark-grey" inert>
              {label}
            </span>{" "}
            <span>{item.question}</span>
          </span>
          <span
            aria-hidden="true"
            className="relative grid size-24 shrink-0 place-items-center rounded-2 bg-white/10 transition-colors group-hover:bg-white/20"
          >
            <span className="h-px w-10 bg-current" />
            <span
              className="absolute h-10 w-px bg-current transition-transform duration-300 ease-out"
              style={{ transform: open ? "rotate(90deg)" : "none" }}
            />
          </span>
        </button>
      </h3>
      <FaqPanel id={panelId} labelledBy={buttonId} open={open}>
        <div className="w-full pb-24 text-body-20 text-ghost-grey">
          <div className="flex w-full flex-col gap-[1em]">
            {item.answer.map((paragraph, i) => (
              <div key={i} className="empty:h-[1lh]" data-text="true">
                {renderParagraph(paragraph)}
              </div>
            ))}
          </div>
        </div>
      </FaqPanel>
    </li>
  );
}

/**
 * FAQ: sticky left column (heading + CTA pinned to the column bottom on lg) beside a
 * single-open accordion (Q.001 open initially). Dim GlyphField phrase backdrop behind.
 */
export function FaqSection({ content }: { content: FaqContent }) {
  const { id = "faq", title, cta, items, numberPrefix = "Q.", defaultOpenIndex = 0, glyph } = content;
  const [openIndex, setOpenIndex] = useState<number | null>(defaultOpenIndex);

  return (
    <div
      id={id}
      data-page-builder-section="faqSection"
      className="relative isolate bg-black px-16 py-72 text-white lg:px-80 lg:py-160"
    >
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-1 bg-black">
        {glyph ? (
          <DeferredMount>
            <GlyphField
              model={glyph.model}
              phrase={glyph.phrase}
              backgroundOnly
              interactive={false}
              entrance={false}
              maxFps={30}
            />
          </DeferredMount>
        ) : null}
        <div aria-hidden="true" className="absolute inset-0 bg-black-deep/30" />
      </div>
      <div className="grid grid-cols-1 gap-x-16 gap-y-64 lg:grid-cols-12 lg:gap-y-32">
        <div className="contents lg:sticky lg:top-80 lg:col-span-4 lg:flex lg:max-h-[calc(100svh-(--spacing(160)))] lg:flex-col lg:justify-between lg:self-stretch">
          <Reveal as="h2" className="text-balance font-medium text-headline-10">
            {title}
          </Reveal>
          {cta ? (
            <div className="order-last lg:order-0">
              <span className="contents">
                <CaButton
                  leftText={cta.leftText}
                  rightText={cta.rightText}
                  variant={cta.variant ?? "light"}
                  showPulseDot={cta.pulse}
                  href={cta.href}
                  external={cta.external}
                />
              </span>
            </div>
          ) : null}
        </div>
        <ul className="flex flex-col lg:col-span-7 lg:col-start-6">
          {items.map((item, i) => (
            <FaqRow
              key={i}
              item={item}
              label={`${numberPrefix}${String(i + 1).padStart(3, "0")} /`}
              open={openIndex === i}
              onToggle={() => setOpenIndex((prev) => (prev === i ? null : i))}
            />
          ))}
        </ul>
      </div>
    </div>
  );
}

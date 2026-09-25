"use client";

import { Fragment, useEffect, useId, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";
import { Connector } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Connector";
import { Odometer } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Odometer";
import { Reveal } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Reveal";
import { usePrefersReducedMotion } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/hooks";
import type { LearnMoreContent, ReadmeParagraph, ReadmeSection } from "./LearnMore";

/**
 * Mount/visible pair for CSS-transition presence (AnimatePresence-like). `present` turns true as
 * soon as `open` does and stays true for `exitMs` after it turns false; `visible` flips two frames
 * after mount so the enter transition runs from the hidden state.
 */
export function usePresence(open: boolean, exitMs: number) {
  const [prevOpen, setPrevOpen] = useState(open);
  const [present, setPresent] = useState(open);
  const [entered, setEntered] = useState(false);

  if (open !== prevOpen) {
    setPrevOpen(open);
    if (open) setPresent(true);
  }

  useEffect(() => {
    if (open) {
      let inner = 0;
      const outer = requestAnimationFrame(() => {
        inner = requestAnimationFrame(() => setEntered(true));
      });
      return () => {
        cancelAnimationFrame(outer);
        cancelAnimationFrame(inner);
      };
    }
    const timer = window.setTimeout(() => {
      setPresent(false);
      setEntered(false);
    }, exitMs);
    return () => window.clearTimeout(timer);
  }, [open, exitMs]);

  return { present, visible: open && entered };
}

const SLIDE_EASE = "cubic-bezier(0.23, 1, 0.32, 1)";

const CLOSE_BUTTON =
  "inline-flex w-fit min-w-0 shrink-0 cursor-pointer items-end whitespace-nowrap font-mono text-caption-10 uppercase [--odometer-progress:0] motion-safe:hover:[--odometer-progress:1] disabled:pointer-events-none disabled:opacity-50 disabled:grayscale *:data-label:inline-flex *:data-label:h-22 *:data-label:items-center *:data-label:justify-center *:data-label:rounded-4 *:data-label:px-8 *:data-icon:inline-flex *:data-icon:size-48 *:data-icon:items-center *:data-icon:justify-center *:data-icon:rounded-4 *:data-icon:bg-black *:data-label:bg-black *:data-connector:text-black *:data-icon:text-white *:data-label:text-white *:data-connector:transition-colors *:data-icon:transition-colors *:data-label:transition-colors [&:hover_[data-connector]]:text-black-deep [&:hover_[data-icon]]:bg-black-deep [&:hover_[data-label]]:bg-black-deep flex-col-reverse";

const TOC_BUTTON =
  "[--odometer-progress:0] motion-safe:hover:[--odometer-progress:1] flex w-full min-w-0 cursor-pointer overflow-hidden text-left transition-colors hover:text-black";

const LINK = "underline decoration-from-font decoration-dashed underline-offset-3";

const FOCUSABLE = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])';

const sectionLabel = (section: ReadmeSection) => `${section.number} / ${section.title}`;

/**
 * Odometer label truncated with "…" to the width available (mono font, so one measured glyph
 * width decides how many characters fit). The invisible full-text span is the measuring stick.
 */
function TruncatedOdometer({ text }: { text: string }) {
  const boxRef = useRef<HTMLSpanElement>(null);
  const measureRef = useRef<HTMLSpanElement>(null);
  const [display, setDisplay] = useState(text);

  useEffect(() => {
    const box = boxRef.current;
    const measure = measureRef.current;
    if (!box || !measure) return;
    const update = () => {
      const available = box.clientWidth;
      const full = measure.getBoundingClientRect().width;
      if (available <= 0 || full <= available + 0.5 || text.length === 0) {
        setDisplay(text);
        return;
      }
      const fit = Math.max(1, Math.floor(available / (full / text.length)));
      setDisplay(`${text.slice(0, Math.max(0, fit - 1))}…`);
    };
    const observer = new ResizeObserver(update);
    observer.observe(box);
    observer.observe(measure);
    return () => observer.disconnect();
  }, [text]);

  return (
    <span ref={boxRef} className="relative block w-full min-w-0">
      <span ref={measureRef} aria-hidden="true" className="pointer-events-none absolute whitespace-pre opacity-0">
        {text}
      </span>
      <Odometer text={display} />
    </span>
  );
}

function Paragraph({ segments }: { segments: ReadmeParagraph }) {
  return (
    <Reveal className="empty:h-[1lh]">
      {segments.map((segment, i) => {
        if (typeof segment === "string") return <Fragment key={i}>{segment}</Fragment>;
        if ("image" in segment) {
          return (
            // eslint-disable-next-line @next/next/no-img-element -- 1em inline portrait
            <img
              key={i}
              loading="lazy"
              decoding="async"
              src={segment.image.src}
              alt={segment.image.alt}
              width={100}
              height={100}
              className="max-w-full inline-flex h-[1em] w-auto translate-y-[-0.1em] align-middle"
            />
          );
        }
        const external = !segment.href.startsWith("mailto:");
        return (
          <a
            key={i}
            href={segment.href}
            className={LINK}
            {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
          >
            {segment.text}
          </a>
        );
      })}
    </Reveal>
  );
}

interface DrawerDialogProps {
  content: LearnMoreContent;
  onClose: () => void;
}

/** The dialog body: TOC nav + scrollable README panel. Mounted only while the drawer is present. */
function DrawerDialog({ content, onClose }: DrawerDialogProps) {
  const titleId = useId();
  const reduced = usePrefersReducedMotion();
  const dialogRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [activeId, setActiveId] = useState(content.sections[0]?.id ?? "");

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    const target = dialog.querySelector<HTMLElement>("[data-autofocus]") ?? dialog;
    target.focus({ preventScroll: true });
  }, []);

  useEffect(() => {
    const panel = panelRef.current;
    if (!panel) return;
    const states = new Map<string, boolean>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) states.set(entry.target.id, entry.isIntersecting);
        const first = content.sections.find((section) => states.get(section.id));
        if (first) setActiveId(first.id);
      },
      { root: panel, rootMargin: "0px 0px -50% 0px" },
    );
    for (const section of content.sections) {
      const el = panel.querySelector(`#${CSS.escape(section.id)}`);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, [content.sections]);

  const scrollToSection = (id: string) => {
    const panel = panelRef.current;
    const el = panel?.querySelector<HTMLElement>(`#${CSS.escape(id)}`);
    if (!panel || !el) return;
    const top = panel.scrollTop + el.getBoundingClientRect().top - panel.getBoundingClientRect().top;
    panel.scrollTo({ top, behavior: reduced ? "auto" : "smooth" });
    setActiveId(id);
  };

  const trapFocus = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "Tab") return;
    const dialog = dialogRef.current;
    if (!dialog) return;
    const nodes = Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE));
    const first = nodes[0];
    const last = nodes[nodes.length - 1];
    if (!first || !last) return;
    const current = document.activeElement;
    if (event.shiftKey && (current === first || current === dialog)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && current === last) {
      event.preventDefault();
      first.focus();
    }
  };

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      tabIndex={-1}
      onKeyDown={trapFocus}
      className="pointer-events-auto relative isolate flex h-full w-full flex-col overflow-hidden p-8 text-black outline-none lg:max-w-960 lg:flex-row lg:p-16"
    >
      <div className="relative shrink-0 pb-4 lg:self-start lg:pr-4 lg:pb-0">
        <nav
          aria-label={content.tocLabel}
          className="w-full rounded-8 bg-mid-grey p-16 font-mono text-caption-10 uppercase lg:max-w-182"
        >
          <ul className="flex flex-col gap-8">
            {content.sections.map((section) => {
              const label = sectionLabel(section);
              return (
                <li key={section.id}>
                  <button
                    type="button"
                    aria-label={label}
                    aria-current={activeId === section.id ? "true" : undefined}
                    onClick={() => scrollToSection(section.id)}
                    className={cn(TOC_BUTTON, activeId === section.id ? "text-black" : "text-dark-grey")}
                  >
                    <TruncatedOdometer text={label} />
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>
        <Connector
          orientation="horizontal"
          length={0}
          className="pointer-events-none absolute bottom-0 left-24 w-[66%]! text-mid-grey lg:hidden"
        />
        <Connector
          orientation="vertical"
          length={32}
          className="absolute top-24 right-0 hidden text-mid-grey lg:flex"
        />
      </div>
      <div
        ref={panelRef}
        data-lenis-prevent=""
        className="min-h-0 flex-1 overflow-y-auto overscroll-none rounded-8 bg-mid-grey [&>div]:h-full"
      >
        <div>
          <div className="p-16">
            <div className="mb-48 flex items-start justify-between gap-64 border-black/20 border-b pb-48">
              <div>
                <h2 id={titleId} className="text-balance font-mono text-body-20 uppercase">
                  <Reveal as="span" className="inline-block">
                    {content.title}
                  </Reveal>
                </h2>
                <p className="mt-12 font-mono text-caption-20 text-dark-grey uppercase">
                  <Reveal as="span" className="inline-block">
                    {content.subtitle}
                  </Reveal>
                </p>
              </div>
              <button type="button" className={CLOSE_BUTTON} data-autofocus="true" onClick={onClose}>
                <span data-label="true">
                  <Odometer text={content.close} />
                </span>
                <span data-connector="true" className="flex w-48 justify-center">
                  <Connector orientation="horizontal" length={28} />
                </span>
                <span data-icon="true" aria-hidden="true">
                  X
                </span>
              </button>
            </div>
            <div className="flex flex-col gap-48 divide-y divide-black/20">
              {content.sections.map((section) => (
                <section key={section.id} id={section.id} className="flex flex-col gap-16 pb-64 last:pb-0">
                  <h3 className="font-mono text-caption-20 uppercase">
                    <Reveal as="span" className="inline-block">
                      {sectionLabel(section)}
                    </Reveal>
                  </h3>
                  <div className="flex w-full flex-col gap-[1em] [&_[data-text]>*:not(:first-child)]:indent-0 text-body-10">
                    {section.paragraphs.map((paragraph, i) => (
                      <Paragraph key={i} segments={paragraph} />
                    ))}
                  </div>
                </section>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

interface ReadmeDrawerProps {
  open: boolean;
  onClose: () => void;
  content: LearnMoreContent;
}

/**
 * README drawer portal: a 300ms fading `bg-black/40` backdrop (click closes) and a full-height
 * container sliding in from the right (500ms, CA ease). Rendered only while open or exiting, so
 * nothing is portalled during SSR.
 */
export function ReadmeDrawer({ open, onClose, content }: ReadmeDrawerProps) {
  const reduced = usePrefersReducedMotion();
  const slideMs = reduced ? 10 : 500;
  const fadeMs = reduced ? 10 : 300;
  const { present, visible } = usePresence(open, slideMs);

  if (!present) return null;

  return createPortal(
    <>
      <div
        aria-hidden="true"
        onClick={onClose}
        className={cn("fixed inset-0 z-[60] bg-black/40 transition-opacity", visible ? "opacity-100" : "opacity-0")}
        style={{ transitionDuration: `${fadeMs}ms` }}
      />
      <div
        className="pointer-events-none fixed inset-y-0 right-0 z-[60] flex w-full justify-end"
        style={{
          transform: visible ? "translateX(0)" : "translateX(100%)",
          transition: `transform ${slideMs}ms ${SLIDE_EASE}`,
        }}
      >
        <DrawerDialog content={content} onClose={onClose} />
      </div>
    </>,
    document.body,
  );
}

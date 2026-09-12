"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useLenis } from "lenis/react";
import { Connector } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Connector";
import { Odometer } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Odometer";
import { ReadmeDrawer } from "./ReadmeDrawer";

/** Inline image inside a paragraph (CA: the 1em maintainer portrait). */
export interface ReadmeImageSegment {
  image: { src: string; alt: string };
}

/** Inline link inside a paragraph. `mailto:` links open in place, everything else in a new tab. */
export interface ReadmeLinkSegment {
  text: string;
  href: string;
}

export type ReadmeSegment = string | ReadmeImageSegment | ReadmeLinkSegment;

/** One paragraph: plain strings, inline links and inline images, rendered in order. */
export type ReadmeParagraph = readonly ReadmeSegment[];

export interface ReadmeSection {
  /** DOM id of the `<section>` (TOC scroll target). */
  id: string;
  /** "001"; the TOC and heading read `${number} / ${title}`. */
  number: string;
  title: string;
  paragraphs: readonly ReadmeParagraph[];
}

export interface LearnMoreContent {
  /** Widget label pill (CA: "Learn more"). */
  trigger: string;
  /** Drawer heading (CA: "README ╱ The content architecture"). */
  title: string;
  subtitle: string;
  /** Close button label (CA: "Close"). */
  close: string;
  /** aria-label of the TOC nav (CA: "Sections"). */
  tocLabel: string;
  sections: readonly ReadmeSection[];
}

const WIDGET_BUTTON =
  "inline-flex w-fit min-w-0 shrink-0 cursor-pointer items-end whitespace-nowrap font-mono text-caption-10 uppercase [--odometer-progress:0] motion-safe:hover:[--odometer-progress:1] disabled:pointer-events-none disabled:opacity-50 disabled:grayscale *:data-label:inline-flex *:data-label:h-22 *:data-label:items-center *:data-label:justify-center *:data-label:rounded-4 *:data-label:px-8 *:data-icon:inline-flex *:data-icon:size-48 *:data-icon:items-center *:data-icon:justify-center *:data-icon:rounded-4 *:data-icon:bg-ghost-grey *:data-label:bg-ghost-grey *:data-connector:text-ghost-grey *:data-icon:text-black *:data-label:text-black *:data-connector:transition-colors *:data-icon:transition-colors *:data-label:transition-colors [&:hover_[data-connector]]:text-white [&:hover_[data-icon]]:bg-white [&:hover_[data-label]]:bg-white flex-col";

/**
 * Fixed bottom-right "Learn more" widget (label pill, connector, 48px "+" square) that opens the
 * README drawer. Opening locks page scroll (html[data-scroll-locked] + lenis.stop()); closing
 * restores it and returns focus to the widget.
 */
export function LearnMore({ content }: { content: LearnMoreContent }) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const lenis = useLenis();

  const close = useCallback(() => {
    setOpen(false);
    triggerRef.current?.focus({ preventScroll: true });
  }, []);

  useEffect(() => {
    if (!open) return;
    const root = document.documentElement;
    root.dataset.scrollLocked = "";
    lenis?.stop();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      delete root.dataset.scrollLocked;
      lenis?.start();
    };
  }, [open, lenis, close]);

  return (
    <>
      <div className="fixed right-8 bottom-8 z-4 lg:right-16 lg:bottom-16">
        <button
          ref={triggerRef}
          type="button"
          className={WIDGET_BUTTON}
          aria-haspopup="dialog"
          aria-expanded={open}
          onClick={() => setOpen(true)}
        >
          <span data-label="true">
            <Odometer text={content.trigger} />
          </span>
          <span data-connector="true" className="flex w-48 justify-center">
            <Connector orientation="horizontal" length={28} />
          </span>
          <span data-icon="true" aria-hidden="true">
            +
          </span>
        </button>
      </div>
      <ReadmeDrawer open={open} onClose={close} content={content} />
    </>
  );
}

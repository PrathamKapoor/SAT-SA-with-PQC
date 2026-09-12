"use client";

import { useCallback, useEffect, useRef } from "react";
import { useLenis } from "lenis/react";
import { DeferredMount } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/DeferredMount";
import {
  EmailCapture,
  type EmailCaptureCopy,
} from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/EmailCapture";
import { GlyphField } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/GlyphField";
import type { GlyphFieldModel } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/glyph-model";
import { Odometer } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Odometer";
import { PulseDot } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/PulseDot";

export interface FooterLink {
  label: string;
  href: string;
  /** Orange status dot after the label (CA: "Get access"). */
  pulse?: boolean;
  /** Opens in a new tab (`target="_blank"`). */
  external?: boolean;
}

export interface FooterContent {
  /** Newsletter form copy (shared `EmailCapture`). Omit to drop the form column. */
  newsletter?: EmailCaptureCopy;
  /** `aria-label` of the footer nav (CA: "Footer"). */
  navLabel: string;
  links: readonly FooterLink[];
  /** Renders "© {year} {owner}". */
  copyright: { year: string; owner: string };
  /** Small credit link under the copyright (opens in a new tab). */
  credit?: { label: string; href: string };
  /** Backdrop phrase field. */
  glyph: { model: GlyphFieldModel; phrase: string };
}

/** Content rises from 40% of the footer height to 0 while the footer is uncovered. */
const PARALLAX_FACTOR = 0.4;
/** Black overlay opacity while the footer is fully covered; fades to 0 when fully revealed. */
const OVERLAY_MAX_OPACITY = 0.7;

const LINK_CLASS =
  "[--odometer-progress:0] motion-safe:hover:[--odometer-progress:1] inline-flex items-center gap-8 font-mono text-caption-20 uppercase transition-colors hover:text-current";

function FooterNavLink({ link }: { link: FooterLink }) {
  return (
    <a
      className={LINK_CLASS}
      href={link.href}
      {...(link.external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
    >
      <Odometer text={link.label} />
      {link.pulse ? <PulseDot className="relative" /> : null}
    </a>
  );
}

/**
 * Sticky reveal footer. `<main>` (z-1) scrolls over this `sticky bottom-0 z-0` footer; while it is
 * uncovered the content translates from 40% of the footer height to 0 and a black overlay fades
 * from 0.7 to 0. Transform and opacity are written straight to the DOM (no per-frame React state).
 */
export function SiteFooter({ content }: { content: FooterContent }) {
  const { newsletter, navLabel, links, copyright, credit, glyph } = content;
  const footerRef = useRef<HTMLElement>(null);
  const parallaxRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const reducedMotion = useRef(false);

  const update = useCallback(() => {
    const footer = footerRef.current;
    const parallax = parallaxRef.current;
    const overlay = overlayRef.current;
    if (!footer || !parallax || !overlay) return;

    const height = footer.offsetHeight;
    if (height <= 0) return;
    // A sticky element's rect reports its stuck position, so derive the in-flow top from the
    // container instead: the footer is the last child, so its natural top is container bottom − height.
    const container = footer.parentElement;
    const naturalTop = container ? container.getBoundingClientRect().bottom - height : footer.getBoundingClientRect().top;
    const progress = Math.min(1, Math.max(0, (window.innerHeight - naturalTop) / height));
    const hidden = 1 - progress;

    const offset = reducedMotion.current ? 0 : hidden * PARALLAX_FACTOR * height;
    parallax.style.transform = `translate3d(0px, ${offset.toFixed(1)}px, 0px)`;
    overlay.style.opacity = (hidden * OVERLAY_MAX_OPACITY).toFixed(3);
  }, []);

  // Lenis drives the page scroll; its callback fires on every smooth-scroll frame.
  useLenis(update, [update]);

  // Fallback for native scroll (no Lenis, touch) plus resizes of the viewport or the footer.
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onMotionChange = () => {
      reducedMotion.current = media.matches;
      update();
    };
    reducedMotion.current = media.matches;

    let frame = 0;
    const schedule = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(() => {
        frame = 0;
        update();
      });
    };

    update();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    media.addEventListener("change", onMotionChange);
    const observer = new ResizeObserver(schedule);
    if (footerRef.current) observer.observe(footerRef.current);

    return () => {
      if (frame) window.cancelAnimationFrame(frame);
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      media.removeEventListener("change", onMotionChange);
      observer.disconnect();
    };
  }, [update]);

  return (
    <footer ref={footerRef} className="sticky bottom-0 z-0 overflow-hidden bg-black px-16 py-72 text-white lg:p-80">
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
      <div ref={parallaxRef} className="will-change-transform">
        <div className="flex flex-col justify-between gap-32 lg:gap-64">
          <div className="flex flex-col gap-32 lg:flex-row lg:items-start lg:justify-between lg:gap-64">
            {newsletter ? (
              <div className="flex w-full flex-col gap-16 lg:max-w-md">
                <EmailCapture copy={newsletter} buttonVariant="light" />
              </div>
            ) : null}
            <nav aria-label={navLabel} className="flex flex-col gap-y-12 lg:items-end">
              {links.map((link) => (
                <FooterNavLink key={`${link.label}-${link.href}`} link={link} />
              ))}
            </nav>
          </div>
          <div className="flex flex-col gap-24">
            <div aria-hidden="true" className="h-px w-full bg-current/10" />
            <div className="flex flex-col gap-4">
              <p className="font-mono text-caption-20 uppercase">
                © <span className="inline-block w-[4ch] tabular-nums">{copyright.year}</span> {copyright.owner}
              </p>
              {credit ? (
                <a
                  className="w-fit font-mono text-caption-10 uppercase opacity-50 transition-opacity hover:opacity-100"
                  href={credit.href}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {credit.label}
                </a>
              ) : null}
            </div>
          </div>
        </div>
      </div>
      <div
        ref={overlayRef}
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-black will-change-[opacity]"
      />
    </footer>
  );
}

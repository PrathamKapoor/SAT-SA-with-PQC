"use client";

import { Fragment } from "react";
import { AsciiImage, type AsciiGrid } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/AsciiImage";
import { DeferredMount } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/DeferredMount";
import { GlyphField } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/GlyphField";
import type { GlyphFieldModel } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/glyph-model";
import { Reveal } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Reveal";
import { useIsTouchDevice } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/hooks";

/** Inline link inside the intro paragraph (opens in a new tab). */
export interface ShowcaseIntroLink {
  text: string;
  href: string;
}

/** Intro paragraph segment: plain text, or an inline link. */
export type ShowcaseIntroSegment = string | ShowcaseIntroLink;

export interface ShowcaseItem {
  /** Mono uppercase caption under the card; also the ASCII layer's aria-label. */
  label: string;
  /** Card link (new tab). Without it the card renders as a plain block. */
  href?: string;
  /** Precomputed ASCII grid shown until hover (fine pointers). */
  ascii: AsciiGrid;
  /** Real screenshot revealed on hover, and always on touch devices. */
  image: { src: string; alt: string };
}

export interface ShowcaseContent {
  /** Section anchor id (nav "Showcase" target). Defaults to "showcase". */
  id?: string;
  title: string;
  /** One paragraph, rendered inline as text and link segments. */
  intro: readonly ShowcaseIntroSegment[];
  /** Cards: 1 column on mobile, 2 on lg. */
  items: readonly ShowcaseItem[];
  /** Backdrop phrase field. */
  glyph: { model: GlyphFieldModel; phrase: string };
}

const INTRO_LINK_CLASS = "underline decoration-from-font decoration-dashed underline-offset-3";

const IMAGE_CLASS =
  "max-w-full pointer-events-none absolute inset-0 size-full object-cover opacity-0 transition-opacity duration-500 ease-out group-hover:opacity-100 group-data-[active=true]:opacity-100 motion-reduce:transition-none";

function ShowcaseCard({ item, active }: { item: ShowcaseItem; active: boolean }) {
  const body = (
    <>
      <div>
        <div className="relative w-full mb-12 aspect-video">
          <AsciiImage {...item.ascii} label={item.label} className="absolute inset-0" />
          {/* eslint-disable-next-line @next/next/no-img-element -- lazy screenshot layer, sized by its container */}
          <img
            loading="lazy"
            decoding="async"
            alt={item.image.alt}
            src={item.image.src}
            aria-hidden="true"
            className={IMAGE_CLASS}
          />
        </div>
      </div>
      <h3 className="font-mono text-caption-20 uppercase">
        <Reveal as="span" className="inline-block">
          {item.label}
        </Reveal>
      </h3>
    </>
  );

  if (!item.href) {
    return (
      <div className="group block" data-active={active}>
        {body}
      </div>
    );
  }

  return (
    <a className="group block" target="_blank" rel="noopener noreferrer" href={item.href} data-active={active}>
      {body}
    </a>
  );
}

/**
 * Showcase: headline + intro over a phrase-field backdrop, then a grid of ASCII cards that reveal
 * the real screenshot on hover. On coarse pointers every card is `data-active`, so the screenshots
 * are always shown.
 */
export function ShowcaseSection({ content }: { content: ShowcaseContent }) {
  const { id = "showcase", title, intro, items, glyph } = content;
  // Server snapshot is false, so SSR/hydration render data-active="false" and touch devices flip after mount.
  const isTouch = useIsTouchDevice();

  return (
    <div
      id={id}
      data-page-builder-section="showcaseSection"
      className="relative isolate bg-black px-16 py-72 text-white lg:px-80 lg:py-160"
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
      <div className="mb-80 flex flex-col gap-16">
        <h2 className="text-balance font-medium text-headline-10">
          <Reveal as="span" className="inline-block">
            {title}
          </Reveal>
        </h2>
        {intro.length > 0 ? (
          <div className="w-full max-w-600 text-body-20 text-ghost-grey">
            <div className="flex w-full flex-col gap-[1em] [&_[data-text]>*:not(:first-child)]:indent-0">
              <Reveal className="empty:h-[1lh]">
                {intro.map((segment, i) =>
                  typeof segment === "string" ? (
                    <Fragment key={i}>{segment}</Fragment>
                  ) : (
                    <a key={i} target="_blank" rel="noopener noreferrer" className={INTRO_LINK_CLASS} href={segment.href}>
                      {segment.text}
                    </a>
                  ),
                )}
              </Reveal>
            </div>
          </div>
        ) : null}
      </div>
      <div className="grid grid-cols-1 gap-x-24 gap-y-32 lg:grid-cols-2 lg:gap-y-64">
        {items.map((item, i) => (
          <ShowcaseCard key={`${item.label}-${i}`} item={item} active={isTouch} />
        ))}
      </div>
    </div>
  );
}

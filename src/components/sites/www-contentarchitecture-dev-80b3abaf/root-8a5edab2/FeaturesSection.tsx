"use client";

import { cn } from "@/lib/utils";
import { DeferredMount } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/DeferredMount";
import { GlyphField } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/GlyphField";
import type { GlyphFieldModel } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/glyph-model";
import { Reveal } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Reveal";
import { useIsDesktop } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/hooks";

export interface FeatureItem {
  /** Mono index before the title ("001"). Defaults to the 1-based position padded to 3 digits. */
  num?: string;
  title: string;
  /** Body copy; "\n" forces a line break (rendered with `whitespace-pre-line`). */
  body: string;
}

export interface FeaturesContent {
  /** Section anchor id. Defaults to "features". */
  id?: string;
  /** Headline; "\n" forces a line break (rendered with `whitespace-pre-line`). */
  title: string;
  /** Intro paragraphs under the headline, one entry per paragraph. */
  intro: readonly string[];
  /** Feature list, laid out as a 3-step zigzag on lg. */
  items: readonly FeatureItem[];
  /** Interactive WebGL glyph backdrop (sticky on lg). */
  glyph: {
    model: GlyphFieldModel;
    /** Uppercase phrase tiled across the glyph grid. */
    phrase: string;
  };
}

/** lg zigzag offset by `index % 3` (literal strings so Tailwind picks them up). */
const ZIGZAG_OFFSETS = ["lg:ml-0", "lg:ml-[20%]", "lg:ml-[40%]"] as const;

function FeaturesBackdrop({ glyph }: { glyph: FeaturesContent["glyph"] }) {
  const isDesktop = useIsDesktop();

  return (
    <div className="absolute inset-0 -z-1">
      <DeferredMount className="size-full lg:sticky lg:top-0 lg:h-svh" placeholder={<div className="size-full bg-black" />}>
        <GlyphField
          model={glyph.model}
          phrase={glyph.phrase}
          modelLayout={isDesktop ? "right" : "bottom"}
          modelMaxWidth={isDesktop ? 0.55 : 1}
        />
      </DeferredMount>
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 bg-black-deep/30" />
    </div>
  );
}

/**
 * Features: a sticky interactive GlyphField backdrop (model on the right on lg, at the bottom on
 * mobile) behind a 5/12 text column (headline, intro, zigzag feature list). The foreground is
 * pointer-events-none with only the text blocks re-enabled, so empty space stays hoverable and
 * clickable on the field underneath.
 */
export function FeaturesSection({ content }: { content: FeaturesContent }) {
  const { id = "features", title, intro, items, glyph } = content;

  return (
    <div id={id} data-page-builder-section="benefitsSection" className="relative isolate min-h-svh pt-72 pb-64 text-white lg:py-160">
      <FeaturesBackdrop glyph={glyph} />
      <div className="pointer-events-none grid grid-cols-1 gap-16 px-16 lg:grid-cols-12 lg:px-80">
        <div className="lg:col-span-5">
          <div className="flex flex-col gap-32">
            <h2 className="pointer-events-auto whitespace-pre-line text-balance font-medium text-headline-10">
              <Reveal as="span" className="inline-block">
                {title}
              </Reveal>
            </h2>
            {intro.length > 0 ? (
              <div className="w-full pointer-events-auto text-body-20 text-ghost-grey">
                <div className="flex w-full flex-col gap-[1em] [&_[data-text]>*:not(:first-child)]:indent-0">
                  {intro.map((paragraph, i) => (
                    <Reveal key={i} className="empty:h-[1lh]">
                      {paragraph}
                    </Reveal>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
          {items.length > 0 ? (
            <ul className="col-span-12 mt-80 flex flex-col gap-64">
              {items.map((item, i) => (
                <li
                  key={`${i}-${item.title}`}
                  className={cn("pointer-events-auto flex flex-col gap-12 lg:max-w-1/2", ZIGZAG_OFFSETS[i % ZIGZAG_OFFSETS.length])}
                >
                  <Reveal as="span" className="inline-block">
                    <h3 className="font-mono text-caption-20 uppercase">
                      {item.num ?? String(i + 1).padStart(3, "0")} / <span>{item.title}</span>
                    </h3>
                  </Reveal>
                  <Reveal as="span" className="inline-block">
                    <p className="whitespace-pre-line text-body-10 text-ghost-grey">{item.body}</p>
                  </Reveal>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
      {/* Mobile: reserves a square below the list so the bottom-anchored glyph model shows clear of the text. */}
      <div className="pointer-events-none aspect-square lg:hidden" />
    </div>
  );
}

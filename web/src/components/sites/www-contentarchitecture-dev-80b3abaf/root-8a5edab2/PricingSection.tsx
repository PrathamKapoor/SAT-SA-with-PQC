"use client";

import { Fragment, useRef } from "react";
import { CaButton } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/CaButton";
import { PulseDot } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/PulseDot";
import { Reveal } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Reveal";
import { useInView, usePrefersReducedMotion } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/hooks";

export interface PricingPrice {
  /** Static symbol before the digits, e.g. "€". */
  currency: string;
  /** Digits (non-digit characters such as "," render static), e.g. "399". */
  amount: string;
}

export interface PricingCta {
  leftText?: string;
  rightText?: string;
  href: string;
  /** Orange pulse dot in the button's top-right corner. */
  pulse?: boolean;
  /** Open in a new tab. */
  external?: boolean;
}

export interface PricingEdition {
  /** Chip in the top-left of the price block, e.g. "Next.js". */
  tag: string;
  /** Status chip in the top-right (with a pulse dot). Omit to hide it. */
  status?: string;
  price: PricingPrice;
  /** Struck-through compare-at price. */
  compareAt?: PricingPrice;
  /** Optional mono line after the prices (empty on CA). */
  priceNote?: string;
  /** Numbered spec lines (001, 002, …). */
  specs: readonly string[];
  cta: PricingCta;
}

/** A run of text, or an inline link. */
export type PricingRichSegment = string | { text: string; href: string };

export interface PricingContent {
  /** Headline; "\n" forces a line break. */
  title: string;
  trusted?: {
    /** Overlapping avatars, first on top. Decorative (the row is aria-hidden). */
    avatars: readonly { src: string; alt?: string }[];
    label: string;
  };
  /** Rendered as N cards (2 columns on lg). */
  editions: readonly PricingEdition[];
  includes?: {
    title: string;
    /** Numbered items (001, 002, …), 2 CSS columns on lg. */
    items: readonly string[];
    /** Small print paragraphs under the list; each paragraph is a list of segments. */
    notes?: readonly (readonly PricingRichSegment[])[];
  };
}

const REEL_DURATION_MS = 900;
const REEL_STAGGER_MS = 60;
const REEL_EASE = "cubic-bezier(0.23,1,0.32,1)";
const DIGITS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] as const;

function formatIndex(index: number) {
  return String(index + 1).padStart(3, "0");
}

/** One digit column: rolls from 0 to `digit` when `active`. */
function DigitReel({ digit, active, delay }: { digit: number; active: boolean; delay: number }) {
  return (
    <span className="relative inline-block h-[1em] overflow-hidden align-baseline leading-[1em]">
      <span className="invisible">{digit}</span>
      <span
        className="absolute inset-x-0 top-0 flex flex-col motion-safe:transition-transform"
        style={{
          transform: `translateY(-${active ? digit : 0}em)`,
          transitionDuration: `${REEL_DURATION_MS}ms`,
          transitionTimingFunction: REEL_EASE,
          transitionDelay: `${delay}ms`,
        }}
      >
        {DIGITS.map((d) => (
          <span key={d} className="block h-[1em] leading-[1em]" aria-hidden={d === digit ? undefined : true}>
            {d}
          </span>
        ))}
      </span>
    </span>
  );
}

function PriceReel({ price, active }: { price: PricingPrice; active: boolean }) {
  let digitIndex = 0;
  return (
    <span className="inline-flex">
      <span className="sr-only">{`${price.currency}${price.amount}`}</span>
      <span aria-hidden="true" className="flex items-center">
        <span>{price.currency}</span>
        {Array.from(price.amount).map((char, i) => {
          if (!/\d/.test(char)) return <span key={i}>{char}</span>;
          const delay = digitIndex * REEL_STAGGER_MS;
          digitIndex++;
          return <DigitReel key={i} digit={Number(char)} active={active} delay={delay} />;
        })}
      </span>
    </span>
  );
}

function PriceRow({ price, compareAt, note }: { price: PricingPrice; compareAt?: PricingPrice; note?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { rootMargin: "0px 0px -10% 0px" });
  const reduced = usePrefersReducedMotion();
  const active = inView || reduced;

  return (
    <div ref={ref} className="flex flex-wrap items-baseline gap-x-16 gap-y-12">
      <span className="inline-flex text-headline-20 leading-none">
        <PriceReel price={price} active={active} />
      </span>
      {compareAt ? (
        <span className="relative inline-flex font-mono text-caption-10 uppercase">
          <PriceReel price={compareAt} active={active} />
          <span aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-1/2 h-px bg-current" />
        </span>
      ) : null}
      <div className="flex items-center gap-12 font-mono text-caption-10 uppercase">{note}</div>
    </div>
  );
}

const CHIP =
  "inline-flex w-fit min-w-0 shrink-0 items-center whitespace-nowrap rounded-4 px-6 py-4 font-mono text-caption-10 uppercase leading-none tracking-wide bg-current/10";

function BlockJoin() {
  return (
    <div aria-hidden="true" className="flex justify-center">
      <div className="h-4 w-[90%] border-x border-black" />
    </div>
  );
}

function EditionCard({ edition }: { edition: PricingEdition }) {
  const { tag, status, price, compareAt, priceNote, specs, cta } = edition;
  return (
    <div className="relative isolate flex h-full flex-col text-white">
      <div className="flex flex-col gap-12 p-16 lg:p-32 rounded-8 bg-black">
        <div className="flex items-center justify-between gap-12 font-mono text-caption-10 uppercase">
          <span className={`${CHIP} gap-6`}>{tag}</span>
          {status ? (
            <span className={`${CHIP} gap-8`}>
              <PulseDot className="relative" />
              {status}
            </span>
          ) : null}
        </div>
        <PriceRow price={price} compareAt={compareAt} note={priceNote} />
      </div>
      <BlockJoin />
      <ul className="flex flex-1 flex-col gap-4 p-16 font-mono text-caption-10 uppercase lg:p-32 rounded-8 bg-black">
        {specs.map((spec, i) => (
          <li key={i} className="flex gap-24">
            <span inert className="text-dark-grey tabular-nums">
              {formatIndex(i)}
            </span>
            <span className="text-ghost-grey">{spec}</span>
          </li>
        ))}
      </ul>
      <BlockJoin />
      <div className="flex flex-col gap-12 rounded-8 bg-black p-16 lg:p-32">
        <CaButton
          variant="light"
          leftText={cta.leftText}
          rightText={cta.rightText}
          href={cta.href}
          showPulseDot={cta.pulse}
          external={cta.external}
        />
      </div>
    </div>
  );
}

/**
 * Pricing: 3-line headline + "trusted by" avatar row, N edition cards (price block, spec list and
 * light split CTA joined by 4px connectors; price digits roll 0 → value on viewport enter), and the
 * full-width "every edition includes" panel. lg: headline/trusted share row 1, cards 2-up in row 2.
 */
export function PricingSection({ content }: { content: PricingContent }) {
  const { title, trusted, editions, includes } = content;

  return (
    <div id="pricing" data-page-builder-section="pricingSection" className="bg-off-white py-72 text-black lg:py-160">
      <div className="grid grid-cols-1 gap-x-16 gap-y-64 px-16 lg:grid-cols-12 lg:px-80">
        <h2 className="whitespace-pre-line text-balance font-medium text-headline-10 lg:col-span-6 lg:row-start-1">
          <Reveal as="span" className="inline-block">
            {title}
          </Reveal>
        </h2>

        {trusted ? (
          <div className="group flex items-center gap-12 lg:col-span-6 lg:col-start-7 lg:row-start-1 lg:self-end lg:justify-self-end">
            {trusted.avatars.length > 0 ? (
              <div aria-hidden="true" className="flex shrink-0 items-center">
                {trusted.avatars.map((avatar, i) => (
                  <div
                    key={avatar.src}
                    className={i === 0 ? "relative" : "relative -ml-10"}
                    style={{ zIndex: trusted.avatars.length - i }}
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element -- 32px decorative avatar */}
                    <img
                      loading="lazy"
                      decoding="async"
                      alt={avatar.alt ?? ""}
                      src={avatar.src}
                      width={32}
                      height={32}
                      className="size-32 shrink-0 rounded-full bg-mid-grey object-cover outline outline-black/20 -outline-offset-1 ring-2 ring-off-white grayscale transition-[filter] duration-300 ease-out group-hover:grayscale-0 motion-reduce:transition-none"
                    />
                  </div>
                ))}
              </div>
            ) : null}
            <p className="font-mono text-caption-10 text-dark-grey uppercase">
              <Reveal as="span" className="inline-block">
                {trusted.label}
              </Reveal>
            </p>
          </div>
        ) : null}

        <div className="grid grid-cols-1 gap-16 lg:col-span-12 lg:row-start-2 lg:grid-cols-2">
          {editions.map((edition, i) => (
            <EditionCard key={`${edition.tag}-${i}`} edition={edition} />
          ))}
        </div>

        {includes ? (
          <div className="flex flex-col gap-16 rounded-8 bg-black p-16 text-white lg:col-span-12 lg:row-start-3 lg:p-32">
            <span className="font-mono text-caption-10 text-dark-grey uppercase">{includes.title}</span>
            <ul className="font-mono text-caption-10 uppercase lg:columns-2 lg:gap-x-64">
              {includes.items.map((item, i) => (
                <li key={i} className="flex break-inside-avoid gap-24 py-2">
                  <span inert className="text-dark-grey tabular-nums">
                    {formatIndex(i)}
                  </span>
                  <span className="text-ghost-grey">{item}</span>
                </li>
              ))}
            </ul>
            {includes.notes && includes.notes.length > 0 ? (
              <div className="font-mono text-mid-grey text-ui">
                <div className="flex w-full flex-col gap-[1em]">
                  {includes.notes.map((paragraph, p) => (
                    <div key={p} className="empty:h-[1lh]" data-text="true">
                      {paragraph.map((segment, s) =>
                        typeof segment === "string" ? (
                          <Fragment key={s}>{segment}</Fragment>
                        ) : (
                          <a
                            key={s}
                            className="underline decoration-from-font decoration-dashed underline-offset-3"
                            href={segment.href}
                          >
                            {segment.text}
                          </a>
                        ),
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}

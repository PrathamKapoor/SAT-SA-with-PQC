"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { LogoMark } from "../shared/icons";
import { Marquee } from "../shared/Marquee";
import { Odometer } from "../shared/Odometer";
import { PulseDot } from "../shared/PulseDot";

export interface SiteNavLink {
  label: string;
  href: string;
  /** Element id tracked by the scroll-spy; links without one never become active. */
  sectionId?: string;
  /** Orange pulse dot (CA: Pricing). */
  pulse?: boolean;
  /** Opens in a new tab. */
  external?: boolean;
}

export interface SiteNavContent {
  /** aria-label of the <nav> landmark (default "Primary"). */
  navLabel?: string;
  homeHref: string;
  /** aria-label of the logo link. */
  logoLabel: string;
  /** Custom logo node; defaults to the CA `LogoMark`. Rendered inside a size-30 (desktop) / size-24 (mobile) box. */
  logo?: ReactNode;
  links: SiteNavLink[];
  /** Text repeated in the ghost-grey marquee strip. */
  marquee: string;
  /** Mobile toggle text (default "Menu"). */
  menuLabel?: string;
  /** Mobile toggle aria-labels (defaults "Open menu" / "Close menu"). */
  openMenuLabel?: string;
  closeMenuLabel?: string;
}

/** marqy measured 14.76s for one content block of 3 items on the live site. */
const MARQUEE_DURATION = 14.76;
const MARQUEE_ITEMS = 3;
/** A section is active once its top crosses 40% of the viewport height. */
const SPY_THRESHOLD = 0.4;

interface SpyState {
  index: number;
  x: number;
  width: number;
  /** Slide between tabs (only when moving from one active tab to another). */
  slide: boolean;
}

const INITIAL_SPY: SpyState = { index: -1, x: 0, width: 0, slide: false };

function NavLogo({ logo, className }: { logo?: ReactNode; className: string }) {
  if (logo === undefined) return <LogoMark aria-hidden="true" className={cn("shrink-0", className)} />;
  return (
    <span aria-hidden="true" className={cn("flex shrink-0 items-center justify-center *:max-h-full *:max-w-full", className)}>
      {logo}
    </span>
  );
}

function MarqueeStrip({ text, className }: { text: string; className?: string }) {
  return (
    <div className={cn("relative h-18 overflow-hidden rounded-2 bg-ghost-grey font-mono text-black text-ui uppercase", className)}>
      <div className="size-full absolute inset-0 flex items-center">
        <Marquee duration={MARQUEE_DURATION} repeat={3} className="motion-safe:animate-fade-in">
          {Array.from({ length: MARQUEE_ITEMS }, (_, i) => (
            <div
              key={i}
              aria-hidden={i > 0 ? true : undefined}
              className="flex gap-[1em] w-auto flex-row items-center gap-y-0 whitespace-nowrap px-[1em]"
            >
              <div className="empty:h-[1lh]">{text}</div>
            </div>
          ))}
        </Marquee>
      </div>
    </div>
  );
}

function linkTargetProps(link: SiteNavLink) {
  return link.external ? { target: "_blank", rel: "noopener noreferrer" } : {};
}

export function SiteNav({ content }: { content: SiteNavContent }) {
  const { links } = content;
  const [spy, setSpy] = useState<SpyState>(INITIAL_SPY);
  const [menuOpen, setMenuOpen] = useState(false);
  const listRef = useRef<HTMLUListElement>(null);
  const itemRefs = useRef<(HTMLLIElement | null)[]>([]);
  const menuId = useId();

  // Scroll-spy: the linked section spanning the 40% viewport line (rAF-throttled). Sections that
  // are not in the nav (Reviews, the banner) clear the tab, as on the live site.
  useEffect(() => {
    let frame = 0;

    const update = () => {
      frame = 0;
      const limit = window.innerHeight * SPY_THRESHOLD;
      let index = -1;
      links.forEach((link, i) => {
        if (!link.sectionId) return;
        const rect = document.getElementById(link.sectionId)?.getBoundingClientRect();
        if (rect && rect.top <= limit && rect.bottom > limit) index = i;
      });
      const item = index >= 0 ? itemRefs.current[index] : null;
      const geometry = item ? { x: item.offsetLeft, width: item.offsetWidth } : null;
      setSpy((prev) => {
        const x = geometry?.x ?? prev.x;
        const width = geometry?.width ?? prev.width;
        if (prev.index === index && prev.x === x && prev.width === width) return prev;
        return { index, x, width, slide: prev.index >= 0 && index >= 0 && prev.index !== index };
      });
    };

    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };

    schedule();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    // Re-measure the tab when the desktop list resizes (font swap, breakpoint change).
    const observer = new ResizeObserver(schedule);
    if (listRef.current) observer.observe(listRef.current);

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      observer.disconnect();
    };
  }, [links]);

  // Escape closes the mobile menu.
  useEffect(() => {
    if (!menuOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [menuOpen]);

  const tabActive = spy.index >= 0;

  return (
    <header className="pointer-events-none fixed inset-x-0 top-0 z-4 flex justify-start p-8 lg:justify-center lg:p-16">
      <nav aria-label={content.navLabel ?? "Primary"}>
        <div className="rounded-8 p-6 shadow-lg ring ring-black-deep transition-colors duration-300 lg:p-8 bg-black-deep bg-dither pointer-events-auto">
          {/* Desktop pill */}
          <div className="hidden flex-col gap-4 overflow-hidden rounded-4 bg-black p-4 ring-1 ring-white/10 lg:flex">
            <ul ref={listRef} className="relative flex items-center font-mono text-caption-10 uppercase">
              <span
                aria-hidden="true"
                className={cn(
                  "pointer-events-none absolute inset-y-0 left-0 rounded-2 bg-white/8 ring-1 ring-white/15 duration-200 ease-out motion-reduce:transition-none",
                  spy.slide ? "transition-[opacity,scale,transform,width]" : "transition-[opacity,scale]",
                  tabActive ? "scale-100 opacity-100" : "scale-95 opacity-0",
                )}
                style={{ transform: `translateX(${spy.x}px)`, width: spy.width }}
              />
              <li className="mr-4">
                <a aria-label={content.logoLabel} className="flex aspect-square h-full items-center text-white" href={content.homeHref}>
                  <NavLogo logo={content.logo} className="size-30" />
                </a>
              </li>
              {links.map((link, i) => {
                const active = spy.index === i;
                return (
                  <li
                    key={link.href}
                    ref={(el) => {
                      itemRefs.current[i] = el;
                    }}
                    className="relative shrink-0"
                  >
                    <a
                      className={cn(
                        "relative z-1 flex h-30 items-center whitespace-nowrap px-12 transition-colors duration-300 [--odometer-progress:0] motion-safe:hover:[--odometer-progress:1]",
                        active ? "text-white" : "text-white/55 hover:text-white",
                      )}
                      href={link.href}
                      aria-current={active ? "location" : undefined}
                      {...linkTargetProps(link)}
                    >
                      <Odometer text={link.label} />
                      {link.pulse ? <PulseDot className="absolute top-6 right-6" /> : null}
                    </a>
                  </li>
                );
              })}
            </ul>
            <MarqueeStrip text={content.marquee} />
          </div>

          {/* Mobile pill */}
          <div className="relative font-mono text-caption-10 uppercase lg:hidden">
            <div className="flex w-fit min-w-160 flex-col overflow-hidden rounded-4 bg-black p-4 ring-1 ring-white/10">
              <div className="flex items-center">
                <a aria-label={content.logoLabel} className="flex items-center text-white" href={content.homeHref}>
                  <NavLogo logo={content.logo} className="size-24" />
                </a>
                <button
                  type="button"
                  aria-expanded={menuOpen}
                  aria-controls={menuId}
                  aria-label={menuOpen ? (content.closeMenuLabel ?? "Close menu") : (content.openMenuLabel ?? "Open menu")}
                  className="group flex flex-1 items-center justify-between gap-24 pl-12 text-white"
                  onClick={() => setMenuOpen((open) => !open)}
                >
                  <span>{content.menuLabel ?? "Menu"}</span>
                  <span
                    aria-hidden="true"
                    className="relative grid size-24 shrink-0 place-items-center rounded-2 bg-white/10 transition-colors group-hover:bg-white/20"
                  >
                    <span className="h-px w-10 bg-current" />
                    <span
                      className={cn(
                        "absolute h-10 w-px bg-current transition-transform duration-300 ease-out motion-reduce:transition-none",
                        menuOpen && "rotate-90 scale-y-0",
                      )}
                    />
                  </span>
                </button>
              </div>

              <div
                id={menuId}
                inert={!menuOpen}
                className={cn(
                  "grid transition-[grid-template-rows,opacity] duration-300 ease-out motion-reduce:transition-none",
                  menuOpen ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
                )}
              >
                <div className="min-h-0 overflow-hidden">
                  <ul className="mt-4 flex flex-col border-t border-white/10 pt-4">
                    {links.map((link, i) => {
                      const active = spy.index === i;
                      return (
                        <li key={link.href}>
                          <a
                            className={cn(
                              "flex items-center gap-8 py-6 transition-colors duration-300",
                              active ? "text-white" : "text-white/55 hover:text-white",
                            )}
                            href={link.href}
                            aria-current={active ? "location" : undefined}
                            onClick={() => setMenuOpen(false)}
                            {...linkTargetProps(link)}
                          >
                            <span>{link.label}</span>
                            {link.pulse ? <PulseDot className="relative" /> : null}
                          </a>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              </div>

              <MarqueeStrip text={content.marquee} className="mt-4" />
            </div>
          </div>
        </div>
      </nav>
    </header>
  );
}

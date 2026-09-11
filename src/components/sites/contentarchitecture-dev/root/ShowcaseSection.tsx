"use client";

import Image from "next/image";
import { useRef } from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";
import {
  SHOWCASE_INTRO,
  SHOWCASE_ITEMS,
  TESTIMONIALS,
} from "@/components/sites/contentarchitecture-dev/root/content";

export function ShowcaseSection() {
  const scrollerRef = useRef<HTMLDivElement>(null);

  const scrollBy = (direction: 1 | -1) => {
    scrollerRef.current?.scrollBy({ left: direction * 480, behavior: "smooth" });
  };

  return (
    <section id="showcase" className="bg-background px-6 py-24 lg:px-16 lg:py-32">
      <div className="mx-auto max-w-6xl">
        <div className="mb-4 flex items-center justify-between gap-4">
          <h2 className="text-balance text-3xl font-medium leading-tight lg:text-5xl">
            The work that gets remembered.
          </h2>
          <span className="hidden shrink-0 font-mono text-xs uppercase tracking-widest text-muted-foreground sm:inline">
            trusted by 40+ engineers
          </span>
        </div>
        <p className="mb-12 max-w-xl text-sm leading-relaxed text-muted-foreground">
          {SHOWCASE_INTRO}
        </p>

        <div className="relative mb-16">
          <div
            ref={scrollerRef}
            className="flex snap-x snap-mandatory gap-4 overflow-x-auto scroll-smooth pb-2 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
          >
            {SHOWCASE_ITEMS.map((item) => (
              <a
                key={item.name}
                href={item.url}
                target="_blank"
                rel="noreferrer"
                className="group relative aspect-video w-[85%] shrink-0 snap-start overflow-hidden rounded-2xl border border-border bg-card sm:w-[60%] lg:w-[44%]"
              >
                <Image
                  src={item.image}
                  alt={item.alt}
                  fill
                  sizes="(min-width: 1024px) 44vw, (min-width: 640px) 60vw, 85vw"
                  className="object-cover transition-transform duration-500 group-hover:scale-105"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/0 to-black/0" />
                <span className="absolute bottom-4 left-4 font-mono text-xs uppercase tracking-widest text-white">
                  {item.name}
                </span>
              </a>
            ))}
          </div>

          <div className="mt-6 flex items-center justify-center gap-3">
            <button
              type="button"
              onClick={() => scrollBy(-1)}
              aria-label="Previous"
              className="inline-flex size-9 items-center justify-center rounded-full border border-border text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              <ArrowLeft className="size-4" />
            </button>
            <button
              type="button"
              onClick={() => scrollBy(1)}
              aria-label="Next"
              className="inline-flex size-9 items-center justify-center rounded-full border border-border text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              <ArrowRight className="size-4" />
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {TESTIMONIALS.map((testimonial) => (
            <figure
              key={testimonial.name}
              className="flex flex-col justify-between gap-6 rounded-2xl border border-border bg-card p-6"
            >
              <blockquote className="text-sm leading-relaxed text-foreground/90">
                &ldquo;{testimonial.quote}&rdquo;
              </blockquote>
              <figcaption className="flex items-center gap-3">
                <Image
                  src={testimonial.avatar}
                  alt={testimonial.name}
                  width={40}
                  height={40}
                  className="size-10 shrink-0 rounded-full bg-muted object-cover"
                />
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{testimonial.name}</p>
                  <p className="truncate text-xs text-muted-foreground">{testimonial.role}</p>
                </div>
              </figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  );
}

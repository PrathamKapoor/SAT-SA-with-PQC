"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { FAQ_ITEMS } from "@/components/sites/contentarchitecture-dev/root/content";

export function FaqSection() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  return (
    <section id="faq" className="bg-background px-6 py-24 lg:px-16 lg:py-32">
      <div className="mx-auto max-w-3xl">
        <h2 className="mb-12 text-balance text-3xl font-medium leading-tight lg:text-5xl">
          Before you buy
        </h2>

        <div className="flex flex-col divide-y divide-border border-t border-border">
          {FAQ_ITEMS.map((item, index) => {
            const isOpen = openIndex === index;
            return (
              <div key={item.number}>
                <button
                  type="button"
                  onClick={() => setOpenIndex(isOpen ? null : index)}
                  aria-expanded={isOpen}
                  className="flex w-full items-center justify-between gap-4 py-5 text-left"
                >
                  <span className="text-sm font-medium sm:text-base">
                    <span className="mr-2 font-mono text-xs text-tertiary">
                      Q.{item.number} /
                    </span>
                    {item.question}
                  </span>
                  <ChevronDown
                    className={cn(
                      "size-4 shrink-0 text-muted-foreground transition-transform",
                      isOpen && "rotate-180"
                    )}
                  />
                </button>
                <div
                  className={cn(
                    "grid transition-all duration-300 ease-in-out",
                    isOpen ? "grid-rows-[1fr] pb-6 opacity-100" : "grid-rows-[0fr] opacity-0"
                  )}
                >
                  <div className="overflow-hidden">
                    <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
                      {item.answer}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

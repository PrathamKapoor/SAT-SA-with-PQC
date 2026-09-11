"use client";

import { useRef } from "react";
import { cn } from "@/lib/utils";
import { DitherFrame } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/DitherFrame";
import { Reveal } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/Reveal";
import { useInView, useTypewriter } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/hooks";

export interface ProblemRow {
  /** Row index label shown in dark grey, e.g. "001". */
  num: string;
  /** Problem description, typed after the number. */
  text: string;
  /** Right-aligned cost, e.g. "~5 HRS". Fades in once the row finishes typing. */
  value?: string;
}

export interface ProblemsContent {
  /** Terminal window title-bar label (rendered uppercase). */
  terminalTitle: string;
  /** Numbered rows, typed in order. */
  rows: ProblemRow[];
  /** Final line typed after a blank spacer row (whitespace is preserved). */
  summary?: string;
  /** Section heading (right column). */
  heading: string;
  /** Body paragraphs under the heading. */
  paragraphs: string[];
}

interface TerminalLine {
  num: string;
  text: string;
  value?: string;
}

const CURSOR_CLASS =
  "ml-px inline-block h-[1em] w-[0.55em] translate-y-[0.15em] animate-cursor-blink bg-current align-baseline";

function Cursor() {
  return <span aria-hidden="true" className={CURSOR_CLASS} />;
}

/** Typed span over an `invisible` copy that reserves the final width. */
function TypedSpan({ full, visible, cursor, className }: { full: string; visible: number; cursor: boolean; className?: string }) {
  return (
    <span className={cn("relative inline-block whitespace-pre", className)}>
      <span className="invisible">{full === "" ? " " : full}</span>
      <span className="absolute inset-y-0 left-0 whitespace-pre">
        {full.slice(0, visible)}
        {cursor ? <Cursor /> : null}
      </span>
    </span>
  );
}

function buildTranscript(content: ProblemsContent) {
  const rows = content.rows.map((row) => [row.num, row.text, row.value].filter(Boolean).join(" "));
  return [...rows, content.summary].filter(Boolean).join(". ");
}

function ProblemsTerminal({ content }: { content: ProblemsContent }) {
  const bodyRef = useRef<HTMLDivElement>(null);
  const inView = useInView(bodyRef, { rootMargin: "0px 0px -10% 0px" });

  const lines: TerminalLine[] = content.rows.map((row) => ({ num: row.num, text: row.text, value: row.value }));
  if (content.summary !== undefined) {
    lines.push({ num: "", text: "" }, { num: "", text: content.summary });
  }

  // One typewriter line per row: the number and the text are typed as one run.
  const typed = lines.map((line) => line.num + line.text);
  const { visibleChars, activeRow, done } = useTypewriter(typed, { charDelay: 18, lineDelay: 90, enabled: inView });
  const cursorRow = done ? lines.length - 1 : activeRow;

  return (
    <DitherFrame title={content.terminalTitle} draggable>
      <div ref={bodyRef} className="scrollbar-thin overflow-x-auto p-16">
        <span className="sr-only">{buildTranscript(content)}</span>
        <div aria-hidden="true" className="flex min-w-max flex-col gap-y-2">
          {lines.map((line, index) => {
            const visible = visibleChars[index] ?? 0;
            const numVisible = Math.min(visible, line.num.length);
            const textVisible = Math.max(0, visible - line.num.length);
            const isCursorRow = index === cursorRow;
            const cursorInNum = isCursorRow && visible < line.num.length;
            const cursorInText = isCursorRow && !cursorInNum;
            const rowDone = visible >= line.num.length + line.text.length;
            return (
              <div key={index} className="flex items-baseline justify-between gap-x-16 whitespace-pre">
                <span className={cn("flex items-baseline", line.num !== "" && "gap-24")}>
                  {line.num !== "" ? (
                    <TypedSpan
                      full={line.num}
                      visible={numVisible}
                      cursor={cursorInNum}
                      className="text-dark-grey tabular-nums"
                    />
                  ) : null}
                  <TypedSpan full={line.text} visible={textVisible} cursor={cursorInText} />
                </span>
                {line.value !== undefined ? (
                  <span
                    className={cn("whitespace-pre transition-opacity duration-200", rowDone ? "opacity-100" : "opacity-0")}
                  >
                    {line.value}
                  </span>
                ) : null}
              </div>
            );
          })}
        </div>
      </div>
    </DitherFrame>
  );
}

export function ProblemsSection({ content }: { content: ProblemsContent }) {
  return (
    <section data-page-builder-section="textTerminalSection" className="bg-off-white py-72 text-black lg:py-160">
      <div className="grid grid-cols-1 gap-x-16 gap-y-32 px-16 lg:grid-cols-12 lg:px-0">
        <div className="order-2 lg:order-1 lg:col-span-5 lg:pl-100">
          <ProblemsTerminal content={content} />
        </div>
        <div className="order-1 flex flex-col gap-32 lg:order-2 lg:col-span-6 lg:col-start-7 lg:pr-80">
          <Reveal as="h2" className="text-balance font-medium text-headline-10">
            {content.heading}
          </Reveal>
          <div className="w-full text-body-20 text-dark-grey">
            <div className="flex w-full flex-col gap-[1em] [&_[data-text]>*:not(:first-child)]:indent-0">
              {content.paragraphs.map((paragraph, index) => (
                <Reveal key={index} className="empty:h-[1lh]">
                  {paragraph}
                </Reveal>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

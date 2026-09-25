import type { ReactNode } from "react";

import type { HighlightMode } from "./model";

/**
 * Tiny line-based highlighter for the repo editor overlay. Returns `<span>`s whose text content,
 * concatenated, is exactly `text` (trailing newline included); unstyled runs are plain spans that
 * inherit the overlay colour. Adjacent runs of the same class are merged, as on the live site.
 *
 * Self-check: highlight("# A\n- `b` **c** [d](e)\n", "markdown") renders
 *   <span class="text-[#9fb6d6]"># A</span><span>\n</span><span class="text-white/35">-</span>
 *   <span> </span><span class="text-[#d6a878]">`b`</span><span> </span><span class="text-white/90">**c**</span>
 *   <span> </span><span class="text-white/75">[d](e)</span><span>\n</span>
 * whose text is the input verbatim.
 */

const HEADING = "text-[#9fb6d6]";
const FENCE = "text-white/40";
const LIST_MARKER = "text-white/35";
const INLINE_CODE = "text-[#d6a878]";
const BOLD = "text-white/90";
const LINK = "text-white/75";
const COMMENT = "text-white/30 italic";

/** Leading indentation, then `-`, `*` or `1.` followed by whitespace or the end of the line. */
const LIST_RE = /^(\s*)([-*]|\d+\.)(?=\s|$)/;
/** `code` | **bold** | [label](url); the leftmost construct wins, no nesting. */
const INLINE_RE = /(`[^`\n]+`)|(\*\*[^*\n]+?\*\*)|(\[[^\]\n]*\]\([^)\n]*\))/g;

type Run = { cls: string | null; text: string };

class Runs {
  readonly list: Run[] = [];

  push(cls: string | null, text: string) {
    if (!text) return;
    const last = this.list[this.list.length - 1];
    if (last && last.cls === cls) last.text += text;
    else this.list.push({ cls, text });
  }
}

function pushInline(runs: Runs, line: string) {
  let index = 0;
  INLINE_RE.lastIndex = 0;
  for (let match = INLINE_RE.exec(line); match; match = INLINE_RE.exec(line)) {
    runs.push(null, line.slice(index, match.index));
    runs.push(match[1] ? INLINE_CODE : match[2] ? BOLD : LINK, match[0]);
    index = match.index + match[0].length;
  }
  runs.push(null, line.slice(index));
}

function markdownRuns(lines: string[], runs: Runs) {
  let inFence = false;
  lines.forEach((line, i) => {
    const newline = i < lines.length - 1 ? "\n" : "";
    const isFence = line.trimStart().startsWith("```");

    if (inFence || isFence) {
      runs.push(FENCE, line);
      // A fence keeps its inner newlines; the one after the closing fence is plain.
      const closes = inFence && isFence;
      inFence = !closes;
      runs.push(inFence ? FENCE : null, newline);
      return;
    }

    if (line.startsWith("#")) {
      runs.push(HEADING, line);
    } else {
      const list = LIST_RE.exec(line);
      if (list) {
        runs.push(null, list[1]);
        runs.push(LIST_MARKER, list[2]);
        pushInline(runs, line.slice(list[0].length));
      } else {
        pushInline(runs, line);
      }
    }
    runs.push(null, newline);
  });
}

function commentRuns(lines: string[], runs: Runs, isComment: (trimmed: string) => boolean) {
  lines.forEach((line, i) => {
    runs.push(isComment(line.trimStart()) ? COMMENT : null, line);
    if (i < lines.length - 1) runs.push(null, "\n");
  });
}

const isSlashComment = (trimmed: string) =>
  trimmed.startsWith("//") || trimmed.startsWith("/*") || trimmed.startsWith("*");

const isHashComment = (trimmed: string) => trimmed.startsWith("#");

export function highlight(text: string, mode: HighlightMode): ReactNode[] {
  const runs = new Runs();
  const lines = text.split("\n");

  if (mode === "markdown") markdownRuns(lines, runs);
  else if (mode === "slash-comments") commentRuns(lines, runs, isSlashComment);
  else if (mode === "hash-comments") commentRuns(lines, runs, isHashComment);
  else runs.push(null, text);

  return runs.list.map((run, i) =>
    run.cls ? (
      <span key={i} className={run.cls}>
        {run.text}
      </span>
    ) : (
      <span key={i}>{run.text}</span>
    ),
  );
}

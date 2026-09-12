import { DitherFrame } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/DitherFrame";

export interface BannerContent {
  /** Optional section anchor id. */
  id?: string;
  /** Frame title-bar label (rendered uppercase). */
  title: string;
  /** Accessible name of the ASCII art (`role="img"`), i.e. the words the art spells. */
  label: string;
  /** Monospace (figlet) art, lines separated by "\n". Rendered verbatim with `whitespace-pre`. */
  art: string;
}

/** Monospace glyph advance in em (Geist Mono ≈ 0.6em per character). */
const GLYPH_ADVANCE_EM = 0.6;

/** `100cqw / N` makes the longest line exactly fill the container: N = longest line × 0.6. */
function artFontSize(art: string) {
  const longest = art.split("\n").reduce((max, line) => Math.max(max, line.length), 0);
  const divisor = Math.max(1, longest) * GLYPH_ADVANCE_EM;
  return `calc(100cqw / ${divisor.toFixed(2)})`;
}

/** "calloutSection": a draggable dithered window holding ASCII art that scales with its container (cqw). */
export function BannerSection({ content }: { content: BannerContent }) {
  const { id, title, label, art } = content;

  return (
    <div id={id} data-page-builder-section="calloutSection" className="bg-off-white px-16 py-72 lg:p-80">
      <DitherFrame title={title} draggable>
        <div className="p-16 @container overflow-hidden">
          <pre
            role="img"
            aria-label={label}
            className="m-0 w-full overflow-hidden whitespace-pre leading-none"
            style={{ fontSize: artFontSize(art) }}
          >
            {art}
          </pre>
        </div>
      </DitherFrame>
    </div>
  );
}

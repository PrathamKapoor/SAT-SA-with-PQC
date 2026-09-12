import type { AsciiGrid } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/AsciiImage";
import { decodeGlyphFieldModel } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/glyph-model";
import type { ReviewsContent } from "../ReviewsSection";
import asciiGrids from "../data/ascii-grids.json";
import glyphPhrases from "../data/glyph-phrases.json";
import orbModel from "../data/orb-model.json";

const AVATARS = "/sites/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/avatars";

function ascii(key: keyof typeof asciiGrids): AsciiGrid {
  const { cells, levels, cols, rows, aspect } = asciiGrids[key];
  return { cells, levels, cols, rows, aspect };
}

export const reviewsContent: ReviewsContent = {
  label: "Testimonials",
  items: [
    {
      quote:
        "“We shipped the Good Fella site on an early version and it saved us tons of time. Six months in, we're still building pages and sections in an afternoon without fighting the setup.”",
      name: "Julian Fella",
      role: "Co-Founder, Good Fella",
      avatar: { ascii: ascii("julian-fella"), src: `${AVATARS}/julian-fella.png` },
    },
    {
      quote:
        "“Edo and I ran a client project on this together. The plumbing was already handled, so the week we'd normally lose to setup went into the creative work the client actually remembers.”",
      name: "Elliott Mangham",
      role: "Founder & Frontend Engineer",
      avatar: { ascii: ascii("elliott-mangham"), src: `${AVATARS}/elliott-mangham.png` },
    },
    {
      quote:
        "“I opened the fetch layer and found the revalidation problem I'd burned two days on last project, already solved and committed. That one folder paid for the whole thing, and the rest is six years of decisions I'd have made the slow way.”",
      name: "Malik Kotb",
      role: "Web Designer & Engineer",
      avatar: { ascii: ascii("malik-kotb"), src: `${AVATARS}/malik-kotb.png` },
    },
  ],
  glyph: { model: decodeGlyphFieldModel(orbModel), phrase: glyphPhrases.phrases.reviews },
};

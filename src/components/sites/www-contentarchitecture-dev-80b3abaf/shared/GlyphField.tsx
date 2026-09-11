"use client";

import { cn } from "@/lib/utils";
import type { GlyphFieldModel } from "./glyph-model";

export interface GlyphFieldProps {
  model: GlyphFieldModel;
  /** Uppercase phrase tiled across the grid (each row starts at a hashed offset). */
  phrase: string;
  atlas?: string;
  /** Where the brightness image sits: right half (desktop) or bottom (mobile). */
  modelLayout?: "right" | "bottom";
  imageFit?: "contain" | "cover";
  /** Max model width as a fraction of the container width (CA features: 0.55 desktop, 1 mobile). */
  modelMaxWidth?: number;
  /** Phrase field only (no image region), used as section backdrops. */
  backgroundOnly?: boolean;
  /** Hover dissolve + click ripples + "Click" cursor label. */
  interactive?: boolean;
  /** Ripple-wave entrance reveal when first entering the viewport. */
  entrance?: boolean;
  /** Frame cap when idle (backdrops use 30). */
  maxFps?: number;
  backgroundColor?: string;
  color?: string;
  className?: string;
}

/**
 * STUB — replaced by the GlyphField builder (WebGL2 instanced glyph grid). Renders the static
 * background so layouts can be built against the final props.
 */
export function GlyphField({ backgroundColor = "#232323", className }: GlyphFieldProps) {
  return <div aria-hidden="true" className={cn("relative size-full overflow-hidden", className)} style={{ backgroundColor }} />;
}

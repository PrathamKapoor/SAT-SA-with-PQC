"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { CursorLabel, setupCursorTracking } from "./CursorLabel";
import { createGlyphFieldScene, type GlyphFieldScene, type GlyphSceneOptions } from "./glyph-field-gl";
import { GLYPH_ATLAS, type GlyphFieldModel } from "./glyph-model";
import { usePrefersReducedMotion } from "./hooks";

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
 * Full-bleed WebGL2 grid of monospace glyphs (one instanced quad per cell). Cell opacity comes from
 * the model's brightness bytes placed in a region of the grid; the rest is a faint phrase texture
 * with ambient twinkle. Interactive fields dissolve under the pointer and ripple on click. Falls
 * back to the plain background colour when WebGL2 is unavailable.
 */
export function GlyphField({
  model,
  phrase,
  atlas = GLYPH_ATLAS,
  modelLayout = "right",
  imageFit = "contain",
  modelMaxWidth = 1,
  backgroundOnly = false,
  interactive = true,
  entrance = true,
  maxFps = 60,
  backgroundColor = "#232323",
  color = "#fff",
  className,
}: GlyphFieldProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const labelRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<GlyphFieldScene | null>(null);
  const optionsRef = useRef<GlyphSceneOptions | null>(null);
  const [isHovering, setIsHovering] = useState(false);
  const reducedMotion = usePrefersReducedMotion();
  // With reduced motion the scene renders one static frame, so the pointer affordance is dropped.
  const pointerEnabled = interactive && !reducedMotion;

  // Declared first so the options exist before the scene effect below runs on mount.
  useEffect(() => {
    const options: GlyphSceneOptions = {
      model,
      phrase,
      atlas,
      modelLayout,
      imageFit,
      modelMaxWidth,
      backgroundOnly,
      entrance,
      maxFps,
      backgroundColor,
      color,
      reducedMotion,
    };
    optionsRef.current = options;
    sceneRef.current?.update(options);
  }, [model, phrase, atlas, modelLayout, imageFit, modelMaxWidth, backgroundOnly, entrance, maxFps, backgroundColor, color, reducedMotion]);

  useEffect(() => {
    const container = containerRef.current;
    const options = optionsRef.current;
    if (!container || !options) return;
    let created: GlyphFieldScene | null = null;
    try {
      created = createGlyphFieldScene(container, options);
    } catch {
      created = null;
    }
    if (!created) return;
    const scene = created;
    sceneRef.current = scene;

    const controller = new AbortController();
    if (interactive) {
      setupCursorTracking({
        container,
        signal: controller.signal,
        labelRef,
        setIsHovering,
        onPointerEnter: (x, y) => scene.pointerEnter(x, y),
        onPointerMove: (x, y) => scene.pointerMove(x, y),
        onPointerLeave: () => scene.pointerLeave(),
        onClick: (x, y) => scene.click(x, y),
      });
    }

    return () => {
      controller.abort();
      scene.destroy();
      if (sceneRef.current === scene) sceneRef.current = null;
    };
  }, [interactive]);

  return (
    <div
      ref={containerRef}
      aria-hidden="true"
      style={{ backgroundColor }}
      className={cn("relative size-full overflow-hidden", pointerEnabled && "cursor-pointer", className)}
    >
      {pointerEnabled ? <CursorLabel labelRef={labelRef} isHovering={isHovering} /> : null}
    </div>
  );
}

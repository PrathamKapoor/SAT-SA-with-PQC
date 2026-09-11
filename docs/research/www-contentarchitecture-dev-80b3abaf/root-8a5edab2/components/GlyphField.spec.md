# GlyphField Specification

## Overview
- **Target file:** `src/components/sites/www-contentarchitecture-dev-80b3abaf/shared/GlyphField.tsx`. It replaces the stub; keep the exported `GlyphFieldProps` interface exactly as is.
- **Screenshots:** `docs/design-references/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/03-features-a-1440.jpeg` and `04-features-b-1440.jpeg` (interactive with a model), plus `06-showcase-1440.jpeg`, `07-reviews-1440.jpeg` and `09-faq-1440.jpeg` (background-only backdrops, very dim).
- **Interaction model:** time-driven (ambient twinkle, entrance wave) plus pointer-driven (hover dissolve, click ripples) when `interactive`.
- **Tech:** raw **WebGL2** with instanced quads. Do not add dependencies. Canvas 2D is only for building textures.

## What it draws
A full-bleed grid of monospace glyph cells on `backgroundColor` (#232323), glyphs in `color` (#fff).
- Every cell shows a character of `phrase`. Each row reads a contiguous run of the phrase starting at a hashed per-row offset: `rowOffset = floor(hash1D(row + 0.5) * phraseLen)` and `char = phrase[(col + rowOffset) mod phraseLen]`. This avoids diagonal banding.
- Cell opacity comes from a brightness model (`model.brightness`, modelCols×modelRows bytes) placed in a "model region" of the grid. Outside the region, brightness = 0.01 (very faint ambient text), which gives the dim phrase texture seen behind the dark sections.
- `backgroundOnly`: there is no model region, so the whole field sits at the background brightness, with ambient twinkle across all cells.

## Textures
1. **Glyph atlas** (canvas 2D → texture, mipmapped):
   - 4 columns × `ceil(atlas.length/4)` rows. Tile width `R = max(8, round(64 * glyphAspect))` px and tile height 64px.
   - Draw white text, `textAlign=center`, `textBaseline=middle`, font `500 47.36px <Geist Mono family from CSS var --font-geist-mono>`. The glyph for atlas index i is centred at `((i%4 + 0.5) * R, (floor(i/4) + 0.58) * 64)`.
   - Atlas index 0 is the blank tile (space).
   - Re-render after `document.fonts.ready`.
2. **Brightness texture:** modelCols×modelRows, R channel = byte / 255, LINEAR filtering, CLAMP_TO_EDGE, no mipmaps.

## Grid layout (recompute on resize via ResizeObserver, debounced 150ms)
- `cellH = 14` css px, `cellW = 14 * glyphAspect`.
- `cols = max(8, round(width / cellW))`, then `cellW = width / cols`.
- Normal mode: `rows = max(8, round(height / 14))`, `cellH = height / rows`, and the canvas equals the container.
- backgroundOnly mode: `rows = ceil(height / 14)`, grown in steps of 16 rows (only reallocate when rows grow, or shrink by more than 32). The canvas height is `rows * 14`, overflowing the container, which has `overflow-hidden`.
- **Model region** (normal mode):
  - `imageFit="cover"`: the region is the whole grid. Crop the texture UVs to keep aspect (`scale`/`offset` so the source keeps `sourceAspect` against the grid aspect `cols*glyphAspect/rows`).
  - `imageFit="contain"` (default):
    - `aspectCells = sourceAspect / glyphAspect`
    - `maxCols = cols * clamp(modelMaxWidth, 0.05, 1)`
    - `regionRows = max(1, round(min(rows, maxCols / aspectCells)))`
    - `regionCols = max(1, min(cols, round(regionRows * aspectCells)))`
    - Layout `"right"`: `x0 = cols - regionCols`, `y0 = round((rows - regionRows) / 2)`.
    - Layout `"bottom"`: `x0 = round((cols - regionCols) / 2)`, `y0 = rows - regionRows`.
- **Entrance centre:** the region centre, or the grid centre in backgroundOnly mode.
- **Radii** (in cell units, with `half = cols / 2`): mouseRadius = 0.35·half, rippleMaxRadius = 1.6·half, rippleWidth = 0.85·half.
- **Distance metric:** `d(a, b) = length(vec2(dx, dy / glyphAspect))`, which compensates for non-square cells.

## Per-cell logic (vertex shader, one instance per cell)
- `h = fract(sin(dot(cell, vec2(127.1, 311.7))) * 43758.5453)` is a stable per-cell hash. `hash1D(x) = fract(sin(x*12.9898)*43758.5453)`.
- **Ripples** (max 16, each 1.8s):
  - `t = elapsed / 1.8`
  - `r = smoothstep(0,1,t) * rippleMaxRadius`
  - `bell = 1 - smoothstep(0, rippleWidth/2, |d - r|)`
  - `life = smoothstep(0,.22,t) * (1 - smoothstep(.78,1,t))`
  - `ripple = max over ripples of bell*life`
- **Hover:** `hover = (1 - smoothstep(0, mouseRadius, d(cell, mouse))) * mouseInfluence`.
- **Masks:**
  - `dimMask = (h < hover*2.5) && hover > .001`
  - `boostMask = (h < ripple*0.5) && ripple > .001`
- **Character:** base phrase char, replaced as follows.
  - **Twinkle:** active when `sin(time*0.18 + h*2π)*.5+.5 >= 0.985` and (cell is in the model, or backgroundOnly). The flip char is a random non-blank glyph re-rolled at 2.5Hz: `1 + floor(hash1D(h*17.13 + floor(time*2.5)*1.7) * (n-1))`.
  - **Ripple scramble** (where boostMask): a random non-blank glyph re-rolled at 24Hz.
- **Brightness:** `b = 0.01` outside the model. Inside: `b = max(0.01, tex(regionUV))`, where `regionUV = (cellInRegion + .5) / regionSize * uvScale + uvOffset`.
- **Opacity:**
  - `op = pow(b, 0.6) * (1 - hover)`
  - if dimMask, `op = 0`
  - if boostMask, `op = 1`
- **Entrance** (only while active):
  - `frac = clamp((d(cell, entranceCentre) - rippleWidth/2) / rippleMaxRadius, 0, 1)`
  - `arrival = (0.5 - sin(asin(clamp(1 - 2*frac, -1, 1)) / 3)) * 1.8`
  - `alpha = clamp((time - start - arrival) / 0.5, 0, 1)`
  - Before the entrance starts, alpha is 0. After `time - start > 2.35s`, alpha is permanently 1.
- **Position:** the quad fills its cell exactly (`cellSize = 2 / gridSize` in NDC, with y flipped).
- **Fragment:** `rgba(color, atlas.a * op)` with blend `SRC_ALPHA, ONE_MINUS_SRC_ALPHA`. Clear to `backgroundColor`, opaque.

## CPU loop and state
- rAF runs only while the element intersects the viewport, the document is visible, and reduced motion is off. Otherwise render one static frame.
- `dt = min(0.05, frameDelta)`, and `time += dt`.
- `mouseInfluence` eases toward the target (1 inside, 0 outside) with factor `1 - exp(-6*dt)`. The mouse position eases with `1 - exp(-14*dt)`.
- **maxFps:** when idle (no ripples, `mouseInfluence < .001`, no entrance), render at most every `1000/maxFps` ms. Otherwise render every frame.
- **Entrance:** when `entrance` is true, start it the first time the element enters the viewport (IntersectionObserver). Also push one ripple at the entrance centre at the same time. With reduced motion or `entrance=false`, skip it (alpha 1 everywhere).
- **interactive:**
  - Use `setupCursorTracking` from `./CursorLabel` on the container. Convert the local pointer px to cells with `x / cellW` and `y / cellH`.
  - Click pushes a ripple at the pointer (drop the oldest beyond 16).
  - Render `<CursorLabel labelRef isHovering />` (default text "Click").
  - The container gets `cursor-pointer`.
- **Cleanup:** cancel rAF, abort listeners, disconnect observers, lose the WebGL context (`WEBGL_lose_context`), and remove the canvas.
- **Fallback:** if WebGL2 is unavailable or the shader fails, keep the plain `backgroundColor` div. Never throw.

## DOM
```tsx
<div ref={container} style={{ backgroundColor }} className={cn("relative size-full overflow-hidden", interactive && "cursor-pointer", className)}>
  {/* canvas appended/managed by the effect: display:block; position:absolute; inset:0; width:100%; height:100% (backgroundOnly: height = rows*14px) */}
  {interactive ? <CursorLabel labelRef={labelRef} isHovering={isHovering} /> : null}
</div>
```
Mark it `aria-hidden` (decorative).

## Usage in the page (for context; not your job)
- **Features:** `<GlyphField model={orb} phrase={features} modelLayout={lg ? "right" : "bottom"} modelMaxWidth={lg ? 0.55 : 1} />` inside a `lg:sticky lg:top-0 lg:h-svh` wrapper, with a `bg-black-deep/30` overlay on top.
- **Backdrops** (showcase, reviews and FAQ): `<GlyphField model={orb} phrase={…} backgroundOnly interactive={false} entrance={false} maxFps={30} />`, wrapped in `pointer-events-none absolute inset-0 -z-1` with a `bg-black-deep/30` overlay.
- **Test data:** `src/components/sites/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/data/orb-model.json` (decode it with `decodeGlyphFieldModel` from `./glyph-model`) and `data/glyph-phrases.json` (`phrases.features`, `phrases.showcase`, and so on; `atlas` equals `GLYPH_ATLAS`). Use `phraseToAtlasIndices` from `./glyph-model`.

## Responsive
The grid adapts to container size automatically. On mobile the page passes `modelLayout="bottom"` and `modelMaxWidth={1}`.

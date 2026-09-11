# SpiralScene Specification

## Overview
- **Target file:** `src/components/sites/www-contentarchitecture-dev-80b3abaf/shared/SpiralScene.tsx`. It replaces the stub; keep `SpiralSceneProps` and add only optional props.
- **Screenshots:** `docs/design-references/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/01-hero-1440.jpeg` (desktop right half) and `20-mobile-hero-390.jpeg` (mobile, 80vh panel under the text).
- **Interaction model:** time-driven rotation, plus pointer hover dissolve, plus press-and-hold → charge → release ripple, plus scroll-velocity spin (Lenis).
- **Tech:** raw **WebGL2**, instanced quads, no new dependencies. Background `#232323`.

## Look
30 concentric rings of monospace glyphs spelling `phrase` (default `"THE CONTENT ARCHITECTURE."`). Glyphs sit tangent to their ring. Alternate rings rotate in opposite directions; inner rings are faster.
- Each ring has a soft angular "band" where letters are visible. Outside the band, slots render as small dots, so the text forms bright arcs over a dotted field.
- Inner rings are slightly dimmer grey (0.85 → 1.0 white).

## Atlas (canvas 2D → mipmapped texture)
- 8 columns × `ceil(phrase.length/8)` rows of 64×64 tiles. White `fillText` with font `400 57.6px <--font-geist-mono family>`, centred at `((i%8 + .5)*64, (floor(i/8) + .55)*64)`.
- The `.` character is drawn as a filled circle of radius 5.76px instead of a glyph.
- Re-render after `document.fonts.ready`.

## Ring generation (once, with Math.random)
For ring `k` in 0…29, with `a = k/29`:
- `radius = 0.06 + 1.39*a` (design units; 1 = half the short… see "Fit" below)
- `speed = (k even ? +1 : -1) * (0.006 + (1-a)*0.029)` rad/s
- `letterSizePx = 14 + 16*a`
- `pxToDesign = 1/540`
- `slots = max(8, floor(2π*radius / (0.6 * letterSizePx * pxToDesign)))`
- `bandCenter` = 15% chance of `rand*2π`, otherwise `0.25 + (rand - .5) * 0.65π`
- `bandHalfWidth = min(.98, 10% chance ? 0.05 + 0.15*rand : 0.25 + 0.35*a + 0.3*rand) * π`
- `bandSoftness = π * (0.07 + 0.13*rand)`

**Slot contents:** walk the slots, placing the phrase letters (skip the "." itself) consecutively, then leave 1–3 empty slots at random, and repeat.
- Slot angle: `θ0 = randomStart + i * 2π/slots`.
- `w = smoothstep(edgeOuter = halfWidth + softness, edgeInner = max(0, halfWidth - softness), |wrapAngle(θ0 - bandCenter)|)`. This is a reversed smoothstep: 1 at the band centre, 0 outside.
- A letter slot shows its letter if `w > .7 || (w >= .3 && rand < w)`, with size `letterSizePx*(0.85 + 0.15w)`. Otherwise the slot is a dot (atlas index of ".", size 5px).

**Instance attributes:** radius, θ0, speed, sizePx, charIdx, ringIdx.

## Fit / coordinates
- `aspect = W/H`. If `aspect >= 1`, `fit = (1, aspect)`; otherwise `fit = (1/aspect, 1)`. Then `ndc = (ringPos + rotatedQuad + tremor) * fit`, centred at (0,0).
- In landscape, radius 1 therefore spans half the width. The outer rings (radius up to 1.45) overflow the edges, which is intended.
- A glyph quad's design size is `sizePx * pxToDesign`, so glyphs scale with the container.
- Pointer px → design: `ndcX = x/W*2-1`, `ndcY = -(y/H*2-1)`, `design = (ndcX/fitX, ndcY/fitY)`.

## Per-glyph (vertex shader)
- **Ripples** (≤16, each 1.8s, max radius 1.6, width 0.85):
  - `t = elapsed/1.8`
  - `wave = smoothstep(0,1,t)*1.6`
  - `bell = 1 - smoothstep(0, .425, |radius - wave|)`
  - `life = smoothstep(0,.22,t)*(1-smoothstep(.78,1,t))`
  - `ripple = max(bell*life)`
- **Effective radius:** `R = radius*(1 - ringGather*0.12) + ripple*0.045`.
- **Position:** `θ = θ0 + time*speed + ringOffset[ring]`, and `pos = (cosθ, sinθ)*R`.
- **Hover:**
  - `hover = (1 - smoothstep(0, 0.35, |pos - mouse|)) * mouseInfluence`
  - `strength = max(hover*2.5, ripple)`
  - `seed = θ0*7.13 + radius*13.97`
  - `thr = fract(sin(seed*12.9898)*43758.5453)`
  - `isDot = thr < strength`
- **Hold glitch:** `tick = floor(time*9)`, `noise = fract(sin(seed*91.7 + tick*7.31)*43758.5453)`, and `isDot |= noise < ringCharge*0.15`. When isDot, show the "." glyph.
- **Size:** `mix(sizePx, 5, isDot) * (1 + ripple*0.5)`. The quad is rotated tangent (angle θ+π/2).
- **Shiver:**
  - `sh = fract(sin(θ0*91.17 + radius*47.91)*24634.6345)`
  - 18% of slots (`sh < .18`) tremble by `(sin(time*(38+sh*14) + sh*271), cos(time*(34+sh*17) + sh*113)) * ringCharge * 0.002`
- **Entrance alpha:**
  - `arrival[ring] = 1.8 * smoothstepInverse(min(1, max(0, radius - 0.425)/1.6))`, where `smoothstepInverse(y) = 0.5 - sin(asin(1-2y)/3)`
  - `alpha = clamp((time - arrival)/0.5, 0, 1)`
- **Fragment:** `rgb = mix(0.85, 1.0, smoothstep(0, .85, clamp(radius,0,1.2)))`, `a = atlas.a * alpha`. Blend SRC_ALPHA/ONE_MINUS_SRC_ALPHA; clear opaque #232323.

## CPU loop
- rAF runs only while intersecting, visible and not reduced motion. Otherwise draw one static frame.
- `dt = min(.05, Δ)`, and `time += dt`. Drop ripples older than 1.8s.
- **Mouse:** `mouseInfluence += (target - mi)*(1-exp(-6dt))`, where target is 1 while hovering. The position eases with `1-exp(-14dt)`.
- **Hold state machine:**
  - `pointerdown` → holding (label "Keep holding").
    - `charge = min(1, charge + dt/0.9)`
    - `creep = 1 - (1-creep)*exp(-dt/4)`
    - When charge first reaches 1, the state becomes charged (label "Release").
  - Not holding: `charge *= exp(-10dt)` and `creep *= exp(-10dt)`.
  - `pointerup` while charged → push ripple `{start: time, strength: 0.7 + 0.6*creep}`, set `releaseStart = time`, then go idle.
  - `pointerleave` → cancel (idle, target 0).
- **Per ring:**
  - `o` (charge) and `n` (gather): while holding, `o += (charge - o)*(1-exp(-14dt))` and `n += (smoothstep(0,1,charge)*creep - n)*(1-exp(-14dt))`.
  - Otherwise decay both with `*= exp(-10dt)`, but only once the release wavefront `1.6*smoothstep(0,1,(time - releaseStart)/1.8) + 0.425` has passed this ring's radius (or no release is running). The spring-back therefore travels outward with the wave.
  - Uniforms: `ringCharge = smoothstep(0,1,o)` and `ringGather = n`.
  - Rotation freeze while charged: `frozen[ring] -= smoothstep(0,1,o) * speed * dt`.
- **Scroll spin:**
  - Read the Lenis velocity with `useLenis((lenis) => { velocityRef.current = lenis.velocity })` from `lenis/react`.
  - Decay `velocity *= exp(-5dt)`, then ease `spin += (min(40, |velocity|) - spin)*(1-exp(-4dt))`.
- **Ring offsets:**
  - `kick = max over ripples of (1 - smoothstep(0, .425, |radius - 1.6*smoothstep(0,1,t)|)) * life * strength`
  - `angVel[ring] += (0.55*kick*sign(speed) + speed*spin) * dt`
  - `smooth[ring] += (angVel[ring] - smooth[ring])*(1-exp(-3dt))`
  - `ringOffset = smooth + frozen`
- **Entrance:** push ripple `{start: 0, strength: 1}` on mount. Under reduced motion, start `time` at 2.3 with no ripple.
- **Resize:** ResizeObserver, debounced 150ms. Use DPR `min(devicePixelRatio, 2)`.
- **Cleanup:** as in GlyphField: cancel rAF, abort listeners, disconnect observers, lose context, remove canvas. **Fallback:** on WebGL2 failure, keep the plain background.

## DOM
```tsx
<div ref={container} className={cn("relative size-full cursor-pointer select-none overflow-hidden bg-black", className)}>
  <CursorLabel labelRef={labelRef} isHovering={isHovering} text={label} />   {/* from ./CursorLabel */}
  {/* canvas appended by effect: absolute inset-0, 100%×100% */}
</div>
```
- Use `setupCursorTracking` from `./CursorLabel` for pointer events.
- `label` is "Click & hold", "Keep holding" or "Release"; on touch devices idle is "Tap & hold" (`useIsTouchDevice` from `./hooks`).
- The container has `aria-hidden` semantics for the canvas; the label is aria-hidden already.

## Usage (context)
- Hero: `<SpiralScene phrase="THE CONTENT ARCHITECTURE." />` fills the absolutely positioned right panel.
- The SAT-SA page will pass its own phrase, e.g. `"SAT-SA · TRUST-SAT."`. Any characters must work: the atlas is built from the phrase, and "." is always the dot.

/**
 * Ring generation, glyph atlas and raw WebGL2 renderer for `SpiralScene`: 30 concentric rings of
 * tangent glyphs drawn as one instanced quad per slot.
 */

export const RING_COUNT = 30;
/** Design units per CSS px of letter size (1 design unit = half the fitted axis). */
export const PX_TO_DESIGN = 1 / 540;
export const MAX_RIPPLES = 16;
/** Seconds a ripple lives. */
export const RIPPLE_DURATION = 1.8;
export const RIPPLE_MAX_RADIUS = 1.6;
/** Half of the 0.85 ripple width. */
export const RIPPLE_HALF_WIDTH = 0.425;
/** Size (px) of a dot slot. */
export const DOT_SIZE_PX = 5;
/** Floats per instance: radius, θ0, speed, sizePx, charIdx, ringIdx. */
export const INSTANCE_STRIDE = 6;

const TAU = Math.PI * 2;
const ATLAS_COLUMNS = 8;
const ATLAS_TILE = 64;
const ATLAS_FONT_SIZE = 57.6;
const ATLAS_DOT_RADIUS = 5.76;

export function smoothstep(edge0: number, edge1: number, x: number) {
  const t = Math.min(1, Math.max(0, (x - edge0) / (edge1 - edge0)));
  return t * t * (3 - 2 * t);
}

function wrapAngle(x: number) {
  const m = (((x + Math.PI) % TAU) + TAU) % TAU;
  return m - Math.PI;
}

export interface SpiralRing {
  radius: number;
  /** rad/s, sign alternates per ring. */
  speed: number;
  letterSizePx: number;
  slots: number;
  bandCenter: number;
  bandHalfWidth: number;
  bandSoftness: number;
}

export interface SpiralModel {
  rings: SpiralRing[];
  /** INSTANCE_STRIDE floats per slot. */
  instances: Float32Array;
  instanceCount: number;
  /** Atlas tile i = atlasChars[i] (the phrase, plus a trailing "." when it has none). */
  atlasChars: string[];
  dotIndex: number;
}

/** Generate the rings and slot instances (random once per mount). */
export function buildSpiralModel(phrase: string, random: () => number = Math.random): SpiralModel {
  const chars = Array.from(phrase);
  const atlasChars = [...chars];
  let dotIndex = atlasChars.indexOf(".");
  if (dotIndex < 0) {
    dotIndex = atlasChars.length;
    atlasChars.push(".");
  }
  const letters: number[] = [];
  chars.forEach((ch, i) => {
    if (ch !== ".") letters.push(i);
  });

  const rings: SpiralRing[] = [];
  const data: number[] = [];
  for (let k = 0; k < RING_COUNT; k++) {
    const a = k / (RING_COUNT - 1);
    const radius = 0.06 + 1.39 * a;
    const speed = (k % 2 === 0 ? 1 : -1) * (0.006 + (1 - a) * 0.029);
    const letterSizePx = 14 + 16 * a;
    const slots = Math.max(8, Math.floor((TAU * radius) / (0.6 * letterSizePx * PX_TO_DESIGN)));
    const bandCenter = random() < 0.15 ? random() * TAU : 0.25 + (random() - 0.5) * 0.65 * Math.PI;
    const bandHalfWidth = Math.min(0.98, random() < 0.1 ? 0.05 + 0.15 * random() : 0.25 + 0.35 * a + 0.3 * random()) * Math.PI;
    const bandSoftness = Math.PI * (0.07 + 0.13 * random());
    rings.push({ radius, speed, letterSizePx, slots, bandCenter, bandHalfWidth, bandSoftness });

    const edgeOuter = bandHalfWidth + bandSoftness;
    const edgeInner = Math.max(0, bandHalfWidth - bandSoftness);
    const start = random() * TAU;
    let cursor = 0;
    let gap = 0;
    for (let i = 0; i < slots; i++) {
      const theta0 = start + (i * TAU) / slots;
      let charIdx = dotIndex;
      let sizePx = DOT_SIZE_PX;
      let letter = -1;
      if (gap > 0) {
        gap--;
      } else if (letters.length > 0) {
        letter = letters[cursor] ?? -1;
        cursor++;
        if (cursor >= letters.length) {
          cursor = 0;
          gap = 1 + Math.floor(random() * 3);
        }
      }
      if (letter >= 0) {
        const w = smoothstep(edgeOuter, edgeInner, Math.abs(wrapAngle(theta0 - bandCenter)));
        if (w > 0.7 || (w >= 0.3 && random() < w)) {
          charIdx = letter;
          sizePx = letterSizePx * (0.85 + 0.15 * w);
        }
      }
      data.push(radius, theta0, speed, sizePx, charIdx, k);
    }
  }
  return { rings, instances: new Float32Array(data), instanceCount: data.length / INSTANCE_STRIDE, atlasChars, dotIndex };
}

/** CSS font shorthand for the atlas (also used to trigger the font load). */
export function spiralAtlasFont(fontFamily: string) {
  return `400 ${ATLAS_FONT_SIZE}px ${fontFamily}`;
}

/**
 * 8 columns × ceil(n/8) rows of 64×64 tiles: white glyphs centred at ((i%8 + .5)·64,
 * (floor(i/8) + .55)·64); "." is a filled circle of radius 5.76px.
 */
export function drawSpiralAtlas(canvas: HTMLCanvasElement, chars: readonly string[], fontFamily: string) {
  const rows = Math.max(1, Math.ceil(chars.length / ATLAS_COLUMNS));
  canvas.width = ATLAS_COLUMNS * ATLAS_TILE;
  canvas.height = rows * ATLAS_TILE;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#fff";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.font = spiralAtlasFont(fontFamily);
  chars.forEach((ch, i) => {
    const x = ((i % ATLAS_COLUMNS) + 0.5) * ATLAS_TILE;
    const y = (Math.floor(i / ATLAS_COLUMNS) + 0.55) * ATLAS_TILE;
    if (ch === ".") {
      ctx.beginPath();
      ctx.arc(x, y, ATLAS_DOT_RADIUS, 0, TAU);
      ctx.fill();
    } else if (ch.trim()) {
      ctx.fillText(ch, x, y);
    }
  });
  return { columns: ATLAS_COLUMNS, rows };
}

const VERTEX_SHADER = `#version 300 es
precision highp float;
precision highp int;

layout(location = 0) in vec2 aCorner;
layout(location = 1) in vec4 aSlot;  // radius, theta0, speed, sizePx
layout(location = 2) in vec2 aGlyph; // charIdx, ringIdx

uniform float uTime;
uniform vec2 uFit;
uniform vec2 uMouse;
uniform float uMouseInfluence;
uniform vec4 uRipples[${MAX_RIPPLES}]; // elapsed, strength
uniform int uRippleCount;
uniform vec4 uRings[${RING_COUNT}];    // offset, charge, gather
uniform vec2 uAtlasGrid;
uniform float uDotIndex;

out vec2 vUv;
out float vAlpha;
out float vShade;

float smoothstepInverse(float y) {
  return 0.5 - sin(asin(clamp(1.0 - 2.0 * y, -1.0, 1.0)) / 3.0);
}

void main() {
  float radius = aSlot.x;
  float theta0 = aSlot.y;
  float speed = aSlot.z;
  float sizePx = aSlot.w;
  vec4 ring = uRings[int(aGlyph.y + 0.5)];
  float ringCharge = ring.y;
  float ringGather = ring.z;

  float ripple = 0.0;
  for (int i = 0; i < ${MAX_RIPPLES}; i++) {
    if (i >= uRippleCount) break;
    float t = uRipples[i].x / ${RIPPLE_DURATION.toFixed(2)};
    float wave = smoothstep(0.0, 1.0, t) * ${RIPPLE_MAX_RADIUS.toFixed(2)};
    float bell = 1.0 - smoothstep(0.0, ${RIPPLE_HALF_WIDTH.toFixed(3)}, abs(radius - wave));
    float life = smoothstep(0.0, 0.22, t) * (1.0 - smoothstep(0.78, 1.0, t));
    ripple = max(ripple, bell * life);
  }

  float R = radius * (1.0 - ringGather * 0.12) + ripple * 0.045;
  float theta = theta0 + uTime * speed + ring.x;
  vec2 pos = vec2(cos(theta), sin(theta)) * R;

  float hover = (1.0 - smoothstep(0.0, 0.35, length(pos - uMouse))) * uMouseInfluence;
  float strength = max(hover * 2.5, ripple);
  float seed = theta0 * 7.13 + radius * 13.97;
  float thr = fract(sin(seed * 12.9898) * 43758.5453);
  bool isDot = thr < strength;
  float tick = floor(uTime * 9.0);
  float noise = fract(sin(seed * 91.7 + tick * 7.31) * 43758.5453);
  isDot = isDot || noise < ringCharge * 0.15;

  float glyph = isDot ? uDotIndex : aGlyph.x;
  float size = mix(sizePx, ${DOT_SIZE_PX.toFixed(1)}, isDot ? 1.0 : 0.0) * (1.0 + ripple * 0.5) * ${PX_TO_DESIGN.toFixed(8)};
  float phi = theta + 1.57079632679;
  float c = cos(phi);
  float s = sin(phi);
  vec2 local = (aCorner - 0.5) * size;
  vec2 quad = vec2(local.x * c - local.y * s, local.x * s + local.y * c);

  float sh = fract(sin(theta0 * 91.17 + radius * 47.91) * 24634.6345);
  vec2 tremor = vec2(0.0);
  if (sh < 0.18) {
    tremor = vec2(sin(uTime * (38.0 + sh * 14.0) + sh * 271.0), cos(uTime * (34.0 + sh * 17.0) + sh * 113.0)) * ringCharge * 0.002;
  }

  float arrival = ${RIPPLE_DURATION.toFixed(2)} * smoothstepInverse(min(1.0, max(0.0, radius - ${RIPPLE_HALF_WIDTH.toFixed(3)}) / ${RIPPLE_MAX_RADIUS.toFixed(2)}));
  vAlpha = clamp((uTime - arrival) / 0.5, 0.0, 1.0);
  vShade = mix(0.85, 1.0, smoothstep(0.0, 0.85, clamp(radius, 0.0, 1.2)));

  float row = floor((glyph + 0.5) / uAtlasGrid.x);
  vec2 tile = vec2(glyph - row * uAtlasGrid.x, row);
  vUv = (tile + vec2(aCorner.x, 1.0 - aCorner.y)) / uAtlasGrid;

  if (vAlpha <= 0.0) {
    gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
    return;
  }
  gl_Position = vec4((pos + quad + tremor) * uFit, 0.0, 1.0);
}
`;

const FRAGMENT_SHADER = `#version 300 es
precision mediump float;

in vec2 vUv;
in float vAlpha;
in float vShade;

uniform sampler2D uAtlas;

out vec4 fragColor;

void main() {
  fragColor = vec4(vec3(vShade), texture(uAtlas, vUv).a * vAlpha);
}
`;

export interface SpiralFrame {
  time: number;
  fit: readonly [number, number];
  /** Design coordinates. */
  mouse: readonly [number, number];
  mouseInfluence: number;
  /** MAX_RIPPLES × (elapsed, strength, 0, 0). */
  ripples: Float32Array;
  rippleCount: number;
  /** RING_COUNT × (offset, charge, gather, 0). */
  rings: Float32Array;
  atlasColumns: number;
  atlasRows: number;
  dotIndex: number;
}

export interface SpiralRenderer {
  uploadAtlas(source: HTMLCanvasElement): void;
  uploadInstances(data: Float32Array): void;
  draw(frame: SpiralFrame, width: number, height: number): void;
  dispose(): void;
}

function compileShader(gl: WebGL2RenderingContext, type: number, source: string) {
  const shader = gl.createShader(type);
  if (!shader) return null;
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    if (process.env.NODE_ENV !== "production") console.warn("[SpiralScene] shader compile failed:", gl.getShaderInfoLog(shader));
    gl.deleteShader(shader);
    return null;
  }
  return shader;
}

function linkProgram(gl: WebGL2RenderingContext) {
  const vs = compileShader(gl, gl.VERTEX_SHADER, VERTEX_SHADER);
  const fs = compileShader(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
  const program = vs && fs ? gl.createProgram() : null;
  if (program && vs && fs) {
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);
  }
  if (vs) gl.deleteShader(vs);
  if (fs) gl.deleteShader(fs);
  if (!program) return null;
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    if (process.env.NODE_ENV !== "production") console.warn("[SpiralScene] program link failed:", gl.getProgramInfoLog(program));
    gl.deleteProgram(program);
    return null;
  }
  return program;
}

/** Largest drawing-buffer dimension this context can render into. */
export function maxSpiralBufferSize(gl: WebGL2RenderingContext) {
  const renderbuffer = Number(gl.getParameter(gl.MAX_RENDERBUFFER_SIZE)) || 4096;
  const viewport = gl.getParameter(gl.MAX_VIEWPORT_DIMS) as Int32Array | null;
  return Math.max(1024, Math.min(renderbuffer, viewport?.[0] ?? renderbuffer, viewport?.[1] ?? renderbuffer));
}

/** #232323 */
const BACKGROUND = 35 / 255;

/** Compile the program and allocate buffers/texture. Returns null when anything fails. */
export function createSpiralRenderer(gl: WebGL2RenderingContext): SpiralRenderer | null {
  const program = linkProgram(gl);
  if (!program) return null;
  const vao = gl.createVertexArray();
  const quadBuffer = gl.createBuffer();
  const instanceBuffer = gl.createBuffer();
  const atlasTexture = gl.createTexture();
  const release = () => {
    gl.deleteProgram(program);
    if (vao) gl.deleteVertexArray(vao);
    if (quadBuffer) gl.deleteBuffer(quadBuffer);
    if (instanceBuffer) gl.deleteBuffer(instanceBuffer);
    if (atlasTexture) gl.deleteTexture(atlasTexture);
  };
  if (!vao || !quadBuffer || !instanceBuffer || !atlasTexture) {
    release();
    return null;
  }

  const stride = INSTANCE_STRIDE * 4;
  gl.bindVertexArray(vao);
  gl.bindBuffer(gl.ARRAY_BUFFER, quadBuffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([0, 0, 1, 0, 0, 1, 1, 1]), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0);
  gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
  gl.bindBuffer(gl.ARRAY_BUFFER, instanceBuffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(INSTANCE_STRIDE), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(1);
  gl.vertexAttribPointer(1, 4, gl.FLOAT, false, stride, 0);
  gl.vertexAttribDivisor(1, 1);
  gl.enableVertexAttribArray(2);
  gl.vertexAttribPointer(2, 2, gl.FLOAT, false, stride, 16);
  gl.vertexAttribDivisor(2, 1);
  gl.bindVertexArray(null);
  gl.bindBuffer(gl.ARRAY_BUFFER, null);

  gl.bindTexture(gl.TEXTURE_2D, atlasTexture);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array(4));
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.bindTexture(gl.TEXTURE_2D, null);

  const u = (name: string) => gl.getUniformLocation(program, name);
  const loc = {
    time: u("uTime"),
    fit: u("uFit"),
    mouse: u("uMouse"),
    mouseInfluence: u("uMouseInfluence"),
    ripples: u("uRipples"),
    rippleCount: u("uRippleCount"),
    rings: u("uRings"),
    atlasGrid: u("uAtlasGrid"),
    dotIndex: u("uDotIndex"),
    atlas: u("uAtlas"),
  };
  gl.useProgram(program);
  gl.uniform1i(loc.atlas, 0);
  gl.useProgram(null);

  let instanceCount = 0;

  return {
    uploadAtlas(source) {
      gl.bindTexture(gl.TEXTURE_2D, atlasTexture);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
      gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, source);
      gl.generateMipmap(gl.TEXTURE_2D);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
      gl.bindTexture(gl.TEXTURE_2D, null);
    },
    uploadInstances(data) {
      gl.bindBuffer(gl.ARRAY_BUFFER, instanceBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
      gl.bindBuffer(gl.ARRAY_BUFFER, null);
      instanceCount = Math.floor(data.length / INSTANCE_STRIDE);
    },
    draw(frame, width, height) {
      gl.viewport(0, 0, width, height);
      gl.disable(gl.DEPTH_TEST);
      gl.clearColor(BACKGROUND, BACKGROUND, BACKGROUND, 1);
      gl.clear(gl.COLOR_BUFFER_BIT);
      if (instanceCount <= 0) return;

      gl.useProgram(program);
      gl.bindVertexArray(vao);
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, atlasTexture);

      gl.uniform1f(loc.time, frame.time);
      gl.uniform2f(loc.fit, frame.fit[0], frame.fit[1]);
      gl.uniform2f(loc.mouse, frame.mouse[0], frame.mouse[1]);
      gl.uniform1f(loc.mouseInfluence, frame.mouseInfluence);
      gl.uniform4fv(loc.ripples, frame.ripples);
      gl.uniform1i(loc.rippleCount, frame.rippleCount);
      gl.uniform4fv(loc.rings, frame.rings);
      gl.uniform2f(loc.atlasGrid, frame.atlasColumns, frame.atlasRows);
      gl.uniform1f(loc.dotIndex, frame.dotIndex);

      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, instanceCount);
      gl.bindVertexArray(null);
    },
    dispose() {
      release();
    },
  };
}

/**
 * Shader sources and raw WebGL2 utilities for `GlyphField`: one instanced quad per glyph cell, a
 * canvas-2D glyph atlas texture and an R8 brightness texture built from the model bytes.
 */

/** Nominal cell height in CSS px. */
export const GLYPH_CELL_HEIGHT = 14;
export const MAX_RIPPLES = 16;
/** Seconds a click / entrance ripple lives. */
export const RIPPLE_DURATION = 1.8;
/** After this many seconds the entrance is over and every cell is fully revealed. */
export const ENTRANCE_DURATION = 2.35;

const ATLAS_COLUMNS = 4;
const ATLAS_TILE_HEIGHT = 64;
const ATLAS_FONT_SIZE = 47.36;

export const GLYPH_VERTEX_SHADER = `#version 300 es
precision highp float;
precision highp int;

layout(location = 0) in vec2 aCorner;
layout(location = 1) in uint aBase;

uniform vec2 uGrid;
uniform float uTime;
uniform float uGlyphAspect;
uniform vec2 uMouse;
uniform float uMouseInfluence;
uniform float uMouseRadius;
uniform float uRippleMaxRadius;
uniform float uRippleWidth;
uniform vec4 uRipples[${MAX_RIPPLES}];
uniform int uRippleCount;
uniform float uBackgroundOnly;
uniform vec4 uRegion;
uniform vec4 uUvTransform;
uniform sampler2D uBrightness;
uniform float uEntranceState;
uniform float uEntranceTime;
uniform vec2 uEntranceCentre;
uniform float uGlyphCount;
uniform vec2 uAtlasGrid;

out vec2 vUv;
out float vOpacity;

const float TAU = 6.28318530718;

float hash1D(float x) {
  return fract(sin(x * 12.9898) * 43758.5453);
}

// Distance in cell widths; divides dy by the glyph aspect to compensate for non-square cells.
float cellDistance(vec2 a, vec2 b) {
  vec2 d = a - b;
  return length(vec2(d.x, d.y / uGlyphAspect));
}

void main() {
  int cols = int(uGrid.x + 0.5);
  vec2 cell = vec2(float(gl_InstanceID % cols), float(gl_InstanceID / cols));
  vec2 centre = cell + 0.5;
  float h = fract(sin(dot(cell, vec2(127.1, 311.7))) * 43758.5453);

  float ripple = 0.0;
  for (int i = 0; i < ${MAX_RIPPLES}; i++) {
    if (i >= uRippleCount) break;
    vec4 rp = uRipples[i];
    float t = rp.z / ${RIPPLE_DURATION.toFixed(2)};
    float r = smoothstep(0.0, 1.0, t) * uRippleMaxRadius;
    float bell = 1.0 - smoothstep(0.0, uRippleWidth * 0.5, abs(cellDistance(centre, rp.xy) - r));
    float life = smoothstep(0.0, 0.22, t) * (1.0 - smoothstep(0.78, 1.0, t));
    ripple = max(ripple, bell * life);
  }

  float hover = (1.0 - smoothstep(0.0, uMouseRadius, cellDistance(centre, uMouse))) * uMouseInfluence;
  bool dimMask = h < hover * 2.5 && hover > 0.001;
  bool boostMask = h < ripple * 0.5 && ripple > 0.001;

  vec2 inRegion = cell - uRegion.xy;
  bool inModel = uRegion.z > 0.0
    && all(greaterThanEqual(inRegion, vec2(0.0)))
    && all(lessThan(inRegion, uRegion.zw));
  float b = 0.01;
  if (inModel) {
    vec2 uv = (inRegion + 0.5) / uRegion.zw * uUvTransform.xy + uUvTransform.zw;
    b = max(0.01, textureLod(uBrightness, uv, 0.0).r);
  }

  float glyph = float(aBase);
  float randomSpan = max(uGlyphCount - 1.0, 1.0);
  bool twinkle = (inModel || uBackgroundOnly > 0.5) && sin(uTime * 0.18 + h * TAU) * 0.5 + 0.5 >= 0.985;
  if (twinkle) glyph = 1.0 + floor(hash1D(h * 17.13 + floor(uTime * 2.5) * 1.7) * randomSpan);
  if (boostMask) glyph = 1.0 + floor(hash1D(h * 29.71 + floor(uTime * 24.0) * 3.13) * randomSpan);

  float op = pow(b, 0.6) * (1.0 - hover);
  if (dimMask) op = 0.0;
  if (boostMask) op = 1.0;

  float alpha = 1.0;
  if (uEntranceState > 1.5) {
    float frac = clamp((cellDistance(centre, uEntranceCentre) - uRippleWidth * 0.5) / uRippleMaxRadius, 0.0, 1.0);
    float arrival = (0.5 - sin(asin(clamp(1.0 - 2.0 * frac, -1.0, 1.0)) / 3.0)) * ${RIPPLE_DURATION.toFixed(2)};
    alpha = clamp((uEntranceTime - arrival) / 0.5, 0.0, 1.0);
  } else if (uEntranceState > 0.5) {
    alpha = 0.0;
  }
  vOpacity = op * alpha;

  vec2 tile = vec2(mod(glyph, uAtlasGrid.x), floor(glyph / uAtlasGrid.x));
  vUv = (tile + aCorner) / uAtlasGrid;

  if (vOpacity <= 0.0) {
    // Fully transparent: collapse the quad outside the clip volume to skip rasterisation.
    gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
    return;
  }
  vec2 pos = (cell + aCorner) * (2.0 / uGrid);
  gl_Position = vec4(pos.x - 1.0, 1.0 - pos.y, 0.0, 1.0);
}
`;

export const GLYPH_FRAGMENT_SHADER = `#version 300 es
precision mediump float;

in vec2 vUv;
in float vOpacity;

uniform sampler2D uAtlas;
uniform vec3 uColor;

out vec4 fragColor;

void main() {
  fragColor = vec4(uColor, texture(uAtlas, vUv).a * vOpacity);
}
`;

export type Rgb = readonly [number, number, number];

/** `fract(sin(x * 12.9898) * 43758.5453)`, matching the shader's hash1D. */
export function hash1D(x: number) {
  const v = Math.sin(x * 12.9898) * 43758.5453;
  return v - Math.floor(v);
}

/** Parse any CSS colour into 0–1 RGB (hex fast path, canvas 2D for everything else). */
export function parseCssColor(value: string, fallback: Rgb): Rgb {
  const hex = /^#([0-9a-f]{3,8})$/i.exec(value.trim());
  if (hex) {
    let digits = hex[1] ?? "";
    if (digits.length === 3 || digits.length === 4) digits = Array.from(digits.slice(0, 3), (d) => d + d).join("");
    if (digits.length === 6 || digits.length === 8) {
      const n = Number.parseInt(digits.slice(0, 6), 16);
      return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
    }
    return fallback;
  }
  try {
    const canvas = document.createElement("canvas");
    canvas.width = 1;
    canvas.height = 1;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) return fallback;
    ctx.fillStyle = "#000";
    ctx.fillStyle = value;
    ctx.fillRect(0, 0, 1, 1);
    const [r = 0, g = 0, b = 0] = ctx.getImageData(0, 0, 1, 1).data;
    return [r / 255, g / 255, b / 255];
  } catch {
    return fallback;
  }
}

/**
 * Draw the glyph atlas: 4 columns × ceil(n/4) rows of R×64 px tiles (R = max(8, round(64·aspect))),
 * white 500-weight mono glyphs centred at ((i%4 + .5)·R, (floor(i/4) + .58)·64). Index 0 stays blank.
 */
export function drawGlyphAtlas(canvas: HTMLCanvasElement, chars: readonly string[], glyphAspect: number, fontFamily: string) {
  const tileWidth = Math.max(8, Math.round(ATLAS_TILE_HEIGHT * glyphAspect));
  const rows = Math.max(1, Math.ceil(chars.length / ATLAS_COLUMNS));
  canvas.width = tileWidth * ATLAS_COLUMNS;
  canvas.height = rows * ATLAS_TILE_HEIGHT;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#fff";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.font = `500 ${ATLAS_FONT_SIZE}px ${fontFamily}`;
  for (let i = 1; i < chars.length; i++) {
    const ch = chars[i];
    if (!ch) continue;
    ctx.fillText(ch, ((i % ATLAS_COLUMNS) + 0.5) * tileWidth, (Math.floor(i / ATLAS_COLUMNS) + 0.58) * ATLAS_TILE_HEIGHT);
  }
  return { columns: ATLAS_COLUMNS, rows };
}

/** CSS font shorthand used for the atlas (also used to trigger the font load). */
export function atlasFont(fontFamily: string) {
  return `500 ${ATLAS_FONT_SIZE}px ${fontFamily}`;
}

/**
 * Per-cell base atlas index: each row reads a contiguous run of the phrase starting at
 * `floor(hash1D(row + .5) · len)`, which avoids diagonal banding.
 */
export function buildBaseGlyphs(cols: number, rows: number, phrase: readonly number[]) {
  const out = new Uint16Array(cols * rows);
  const len = phrase.length;
  if (len === 0) return out;
  for (let row = 0; row < rows; row++) {
    const offset = Math.floor(hash1D(row + 0.5) * len);
    const base = row * cols;
    for (let col = 0; col < cols; col++) out[base + col] = phrase[(col + offset) % len] ?? 0;
  }
  return out;
}

export interface GlyphFrame {
  cols: number;
  rows: number;
  time: number;
  glyphAspect: number;
  mouse: readonly [number, number];
  mouseInfluence: number;
  mouseRadius: number;
  rippleMaxRadius: number;
  rippleWidth: number;
  /** MAX_RIPPLES × (x, y, elapsed, 0). */
  ripples: Float32Array;
  rippleCount: number;
  backgroundOnly: boolean;
  /** x0, y0, cols, rows in cells (cols = 0 means no model region). */
  region: readonly [number, number, number, number];
  /** uv scale x/y, uv offset x/y. */
  uvTransform: readonly [number, number, number, number];
  /** 0 none (alpha 1), 1 pending (alpha 0), 2 active. */
  entranceState: 0 | 1 | 2;
  entranceTime: number;
  entranceCentre: readonly [number, number];
  glyphCount: number;
  atlasColumns: number;
  atlasRows: number;
  color: Rgb;
  background: Rgb;
}

export interface GlyphRenderer {
  uploadAtlas(source: HTMLCanvasElement): void;
  uploadBrightness(bytes: Uint8Array, width: number, height: number): void;
  uploadBaseGlyphs(glyphs: Uint16Array): void;
  draw(frame: GlyphFrame, width: number, height: number): void;
  dispose(): void;
}

function compileShader(gl: WebGL2RenderingContext, type: number, source: string) {
  const shader = gl.createShader(type);
  if (!shader) return null;
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    if (process.env.NODE_ENV !== "production") console.warn("[GlyphField] shader compile failed:", gl.getShaderInfoLog(shader));
    gl.deleteShader(shader);
    return null;
  }
  return shader;
}

function linkProgram(gl: WebGL2RenderingContext, vertexSource: string, fragmentSource: string) {
  const vs = compileShader(gl, gl.VERTEX_SHADER, vertexSource);
  const fs = compileShader(gl, gl.FRAGMENT_SHADER, fragmentSource);
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
    if (process.env.NODE_ENV !== "production") console.warn("[GlyphField] program link failed:", gl.getProgramInfoLog(program));
    gl.deleteProgram(program);
    return null;
  }
  return program;
}

function setTextureParams(gl: WebGL2RenderingContext, minFilter: number) {
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, minFilter);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
}

/** Largest drawing-buffer dimension this context can render into. */
export function maxDrawingBufferSize(gl: WebGL2RenderingContext) {
  const renderbuffer = Number(gl.getParameter(gl.MAX_RENDERBUFFER_SIZE)) || 4096;
  const viewport = gl.getParameter(gl.MAX_VIEWPORT_DIMS) as Int32Array | null;
  const vw = viewport?.[0] ?? renderbuffer;
  const vh = viewport?.[1] ?? renderbuffer;
  return Math.max(1024, Math.min(renderbuffer, vw, vh));
}

/** Compile the program and allocate buffers/textures. Returns null when anything fails. */
export function createGlyphRenderer(gl: WebGL2RenderingContext): GlyphRenderer | null {
  const program = linkProgram(gl, GLYPH_VERTEX_SHADER, GLYPH_FRAGMENT_SHADER);
  if (!program) return null;
  const vao = gl.createVertexArray();
  const quadBuffer = gl.createBuffer();
  const instanceBuffer = gl.createBuffer();
  const atlasTexture = gl.createTexture();
  const brightnessTexture = gl.createTexture();
  const release = () => {
    gl.deleteProgram(program);
    if (vao) gl.deleteVertexArray(vao);
    if (quadBuffer) gl.deleteBuffer(quadBuffer);
    if (instanceBuffer) gl.deleteBuffer(instanceBuffer);
    if (atlasTexture) gl.deleteTexture(atlasTexture);
    if (brightnessTexture) gl.deleteTexture(brightnessTexture);
  };
  if (!vao || !quadBuffer || !instanceBuffer || !atlasTexture || !brightnessTexture) {
    release();
    return null;
  }

  gl.bindVertexArray(vao);
  gl.bindBuffer(gl.ARRAY_BUFFER, quadBuffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([0, 0, 1, 0, 0, 1, 1, 1]), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0);
  gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
  gl.bindBuffer(gl.ARRAY_BUFFER, instanceBuffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Uint16Array(2), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(1);
  gl.vertexAttribIPointer(1, 1, gl.UNSIGNED_SHORT, 0, 0);
  gl.vertexAttribDivisor(1, 1);
  gl.bindVertexArray(null);
  gl.bindBuffer(gl.ARRAY_BUFFER, null);

  gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
  gl.bindTexture(gl.TEXTURE_2D, atlasTexture);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array(4));
  setTextureParams(gl, gl.LINEAR);
  gl.bindTexture(gl.TEXTURE_2D, brightnessTexture);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.R8, 1, 1, 0, gl.RED, gl.UNSIGNED_BYTE, new Uint8Array(1));
  setTextureParams(gl, gl.LINEAR);
  gl.bindTexture(gl.TEXTURE_2D, null);

  const u = (name: string) => gl.getUniformLocation(program, name);
  const loc = {
    grid: u("uGrid"),
    time: u("uTime"),
    glyphAspect: u("uGlyphAspect"),
    mouse: u("uMouse"),
    mouseInfluence: u("uMouseInfluence"),
    mouseRadius: u("uMouseRadius"),
    rippleMaxRadius: u("uRippleMaxRadius"),
    rippleWidth: u("uRippleWidth"),
    ripples: u("uRipples"),
    rippleCount: u("uRippleCount"),
    backgroundOnly: u("uBackgroundOnly"),
    region: u("uRegion"),
    uvTransform: u("uUvTransform"),
    brightness: u("uBrightness"),
    entranceState: u("uEntranceState"),
    entranceTime: u("uEntranceTime"),
    entranceCentre: u("uEntranceCentre"),
    glyphCount: u("uGlyphCount"),
    atlasGrid: u("uAtlasGrid"),
    atlas: u("uAtlas"),
    color: u("uColor"),
  };
  gl.useProgram(program);
  gl.uniform1i(loc.atlas, 0);
  gl.uniform1i(loc.brightness, 1);
  gl.useProgram(null);

  let instanceCapacity = 0;

  return {
    uploadAtlas(source) {
      gl.bindTexture(gl.TEXTURE_2D, atlasTexture);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
      gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, source);
      gl.generateMipmap(gl.TEXTURE_2D);
      setTextureParams(gl, gl.LINEAR_MIPMAP_LINEAR);
      gl.bindTexture(gl.TEXTURE_2D, null);
    },
    uploadBrightness(bytes, width, height) {
      const w = Math.max(1, Math.floor(width));
      const h = Math.max(1, Math.floor(height));
      let data = bytes;
      if (data.length !== w * h) {
        data = new Uint8Array(w * h);
        data.set(bytes.subarray(0, w * h));
      }
      gl.bindTexture(gl.TEXTURE_2D, brightnessTexture);
      gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.R8, w, h, 0, gl.RED, gl.UNSIGNED_BYTE, data);
      setTextureParams(gl, gl.LINEAR);
      gl.bindTexture(gl.TEXTURE_2D, null);
    },
    uploadBaseGlyphs(glyphs) {
      gl.bindBuffer(gl.ARRAY_BUFFER, instanceBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, glyphs, gl.STATIC_DRAW);
      gl.bindBuffer(gl.ARRAY_BUFFER, null);
      instanceCapacity = glyphs.length;
    },
    draw(frame, width, height) {
      gl.viewport(0, 0, width, height);
      gl.disable(gl.DEPTH_TEST);
      gl.clearColor(frame.background[0], frame.background[1], frame.background[2], 1);
      gl.clear(gl.COLOR_BUFFER_BIT);
      const count = Math.min(instanceCapacity, frame.cols * frame.rows);
      if (count <= 0) return;

      gl.useProgram(program);
      gl.bindVertexArray(vao);
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, atlasTexture);
      gl.activeTexture(gl.TEXTURE1);
      gl.bindTexture(gl.TEXTURE_2D, brightnessTexture);

      gl.uniform2f(loc.grid, frame.cols, frame.rows);
      gl.uniform1f(loc.time, frame.time);
      gl.uniform1f(loc.glyphAspect, frame.glyphAspect);
      gl.uniform2f(loc.mouse, frame.mouse[0], frame.mouse[1]);
      gl.uniform1f(loc.mouseInfluence, frame.mouseInfluence);
      gl.uniform1f(loc.mouseRadius, frame.mouseRadius);
      gl.uniform1f(loc.rippleMaxRadius, frame.rippleMaxRadius);
      gl.uniform1f(loc.rippleWidth, frame.rippleWidth);
      gl.uniform4fv(loc.ripples, frame.ripples);
      gl.uniform1i(loc.rippleCount, frame.rippleCount);
      gl.uniform1f(loc.backgroundOnly, frame.backgroundOnly ? 1 : 0);
      gl.uniform4f(loc.region, frame.region[0], frame.region[1], frame.region[2], frame.region[3]);
      gl.uniform4f(loc.uvTransform, frame.uvTransform[0], frame.uvTransform[1], frame.uvTransform[2], frame.uvTransform[3]);
      gl.uniform1f(loc.entranceState, frame.entranceState);
      gl.uniform1f(loc.entranceTime, frame.entranceTime);
      gl.uniform2f(loc.entranceCentre, frame.entranceCentre[0], frame.entranceCentre[1]);
      gl.uniform1f(loc.glyphCount, frame.glyphCount);
      gl.uniform2f(loc.atlasGrid, frame.atlasColumns, frame.atlasRows);
      gl.uniform3f(loc.color, frame.color[0], frame.color[1], frame.color[2]);

      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, count);
      gl.bindVertexArray(null);
    },
    dispose() {
      release();
    },
  };
}

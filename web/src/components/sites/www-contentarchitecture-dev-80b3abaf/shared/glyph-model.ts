/** Default glyph atlas used by every CA GlyphField (index 0 is the blank tile). */
export const GLYPH_ATLAS = " ·.ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/+*#@";

export interface GlyphFieldModel {
  /** width / height of the brightness source image. */
  sourceAspect: number;
  modelCols: number;
  modelRows: number;
  /** Glyph cell width / height (CA: 0.55). */
  glyphAspect: number;
  /** modelCols × modelRows brightness bytes (0–255), row-major. */
  brightness: Uint8Array;
}

export interface SerializedGlyphFieldModel {
  sourceAspect: number;
  modelCols: number;
  modelRows: number;
  glyphAspect: number;
  brightnessBase64: string;
}

function base64ToBytes(base64: string) {
  if (typeof atob === "function") {
    const bin = atob(base64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return bytes;
  }
  return Uint8Array.from(Buffer.from(base64, "base64"));
}

export function decodeGlyphFieldModel(model: SerializedGlyphFieldModel): GlyphFieldModel {
  return {
    sourceAspect: model.sourceAspect,
    modelCols: model.modelCols,
    modelRows: model.modelRows,
    glyphAspect: model.glyphAspect,
    brightness: base64ToBytes(model.brightnessBase64),
  };
}

/** Map a phrase onto atlas indices; characters missing from the atlas fall back to the blank tile. */
export function phraseToAtlasIndices(phrase: string, atlas: string = GLYPH_ATLAS) {
  return Array.from(phrase.toUpperCase()).map((ch) => Math.max(0, atlas.indexOf(ch)));
}

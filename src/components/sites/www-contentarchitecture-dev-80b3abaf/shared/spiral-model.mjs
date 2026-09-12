export function buildSpiralGlyphs(phrase, rings, width, height) {
  const result = [];
  const centerX = width / 2;
  const centerY = height / 2;
  for (let ring = 0; ring < rings; ring++) {
    for (let index = 0; index < phrase.length; index++) {
      const angle = (index / phrase.length) * Math.PI * 2 + ring * 0.34;
      const radius = 12 + ring * 10;
      result.push({
        char: phrase[index],
        ring,
        x: ring === 0 && index === 0 ? centerX : centerX + Math.cos(angle) * radius,
        y: ring === 0 && index === 0 ? centerY : centerY + Math.sin(angle) * radius,
      });
    }
  }
  return result;
}

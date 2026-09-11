const GLYPHS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
const STEPS = 5;
const DURATION_MS = 520;
const STAGGER_MS = 28;
const EASE = "cubic-bezier(0.23, 1, 0.32, 1)";

/** Deterministic PRNG (mulberry32) so SSR and client render the same scramble glyphs. */
function seededRandom(seed: number) {
  let t = seed >>> 0;
  return () => {
    t += 0x6d2b79f5;
    let r = Math.imul(t ^ (t >>> 15), t | 1);
    r ^= r + Math.imul(r ^ (r >>> 7), r | 61);
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

function hashString(value: string) {
  let h = 2166136261;
  for (let i = 0; i < value.length; i++) {
    h ^= value.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

interface OdometerProps {
  text: string;
}

/**
 * Slot-machine hover text. Each character is a column of glyphs [char, 4 random, char] that
 * translates up by 5em when an ancestor sets `--odometer-progress: 1` — ancestors opt in with
 * `[--odometer-progress:0] motion-safe:hover:[--odometer-progress:1]`.
 */
export function Odometer({ text }: OdometerProps) {
  const random = seededRandom(hashString(text));
  let columnIndex = 0;

  return (
    <>
      <span className="sr-only">{text}</span>
      <span aria-hidden="true" className="flex items-center">
        {Array.from(text).map((char, i) => {
          if (char === " ") {
            return (
              <span key={i} aria-hidden="true" className="inline-block h-[1em] leading-[1em]">
                {" "}
              </span>
            );
          }
          const glyphs = [char];
          for (let step = 1; step < STEPS; step++) {
            glyphs.push(GLYPHS[Math.floor(random() * GLYPHS.length)] ?? char);
          }
          glyphs.push(char);
          const delay = columnIndex * STAGGER_MS;
          columnIndex++;
          return (
            <span
              key={i}
              aria-hidden="true"
              className="relative inline-block h-[1em] overflow-hidden align-baseline leading-[1em]"
            >
              <span className="invisible">{char}</span>
              <span
                className="absolute inset-x-0 top-0 flex flex-col [transform:translateY(calc(var(--odometer-progress,0)*-5em))] motion-safe:transition-transform"
                style={{
                  transitionDuration: `${DURATION_MS}ms`,
                  transitionDelay: `calc(var(--odometer-progress, 0) * ${delay}ms)`,
                  transitionTimingFunction: EASE,
                }}
              >
                {glyphs.map((glyph, g) => (
                  <span key={g} data-odometer-glyph={glyph} className="block h-[1em] leading-[1em]" />
                ))}
              </span>
            </span>
          );
        })}
      </span>
    </>
  );
}

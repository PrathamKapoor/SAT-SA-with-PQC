/**
 * Decorative instrumentation for the hero: a fixed SVG layer whose stage columns line up with the
 * evidence engine's desktop layout (see evidenceEngine.ts computeLayout). Opacity follows the
 * `--hero-analysis` custom property that HeroVisual publishes each frame.
 */
const STAGES = [
  { x: "55.5%", label: "CSE DATA" },
  { x: "65.5%", label: "ANALYSIS" },
  { x: "77.5%", label: "FINDING" },
  { x: "90.5%", label: "REVIEW" },
];

export function SatSaTexture() {
  return (
    <svg aria-hidden="true" className="satsa-texture pointer-events-none absolute inset-0 hidden size-full lg:block">
      <g className="satsa-texture__frame" stroke="currentColor" strokeWidth="1">
        <line x1="49%" y1="7%" x2="49%" y2="9.5%" />
        <line x1="49%" y1="7%" x2="50.5%" y2="7%" />
        <line x1="97%" y1="93%" x2="97%" y2="90.5%" />
        <line x1="97%" y1="93%" x2="95.5%" y2="93%" />
      </g>
      <text className="satsa-texture__micro" x="51%" y="8.2%">
        FIG. 01 / EVIDENCE FIELD
      </text>

      <g className="satsa-texture__stages">
        <line className="satsa-texture__rail" x1="55.5%" y1="93%" x2="90.5%" y2="93%" />
        <line className="satsa-texture__signal" x1="55.5%" y1="93%" x2="90.5%" y2="93%" />
        {STAGES.map((stage) => (
          <g key={stage.label}>
            <line className="satsa-texture__tick" x1={stage.x} y1="92.2%" x2={stage.x} y2="93.8%" />
            <text className="satsa-texture__micro" x={stage.x} y="96.4%" textAnchor="middle">
              {stage.label}
            </text>
          </g>
        ))}
      </g>
    </svg>
  );
}

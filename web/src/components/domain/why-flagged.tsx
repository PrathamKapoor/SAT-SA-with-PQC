import { fmtPct } from "@/lib/domain/format";
import { FLAGGED_WHEN_TEXT, fmtMeasure, measureFor } from "@/lib/domain/measures";
import type { Finding } from "@/lib/types/domain";

/**
 * Observed vs threshold for a finding. When the two numbers share a unit they
 * are placed on one axis; otherwise they are shown side by side.
 */
export function WhyFlagged({ finding }: { finding: Pick<Finding, "ruleOrCategory" | "statistic" | "threshold" | "effect"> }) {
  const m = measureFor(finding.ruleOrCategory);
  const { statistic: s, threshold: t } = finding;
  const canDraw = m.comparable && s != null && t != null && Number.isFinite(s) && Number.isFinite(t);
  const max = canDraw ? Math.max(s!, t!, 1e-9) * 1.15 : 1;
  const pos = (v: number) => `${Math.max(0, Math.min(100, (v / max) * 100))}%`;

  return (
    <div>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
        <div>
          <dt className="label">{m.statistic}</dt>
          <dd className="num mt-1 text-[24px] leading-none font-semibold text-ink">{fmtMeasure(s, m.unit)}</dd>
        </div>
        <div>
          <dt className="label">{m.threshold}</dt>
          <dd className="num mt-1 text-[24px] leading-none font-semibold text-muted">{fmtMeasure(t, m.thresholdUnit ?? m.unit)}</dd>
        </div>
        {m.boundedEffect && finding.effect != null && (
          <div>
            <dt className="label">Effect</dt>
            <dd className="num mt-1 text-[24px] leading-none font-semibold text-ink">{fmtPct(finding.effect)}</dd>
          </div>
        )}
      </dl>

      {canDraw && (
        <figure className="mt-6" aria-label={`${m.statistic} ${fmtMeasure(s, m.unit)} against ${m.threshold.toLowerCase()} ${fmtMeasure(t, m.unit)}`}>
          <div className="relative h-10">
            <div className="absolute inset-x-0 top-5 h-px bg-line-2" />
            <div className="absolute top-2 h-7 w-px bg-muted" style={{ left: pos(t!) }}>
              <span className="label absolute -top-4 -translate-x-1/2 whitespace-nowrap">{m.threshold}</span>
            </div>
            <div className="absolute top-[14px] size-3 -translate-x-1/2 rounded-full border-2 border-paper bg-attention shadow-[0_0_0_1px] shadow-attention" style={{ left: pos(s!) }} />
            <div
              className="absolute top-[19px] h-[3px] bg-attention/35"
              style={{ left: `min(${pos(s!)}, ${pos(t!)})`, width: `${Math.abs((s! - t!) / max) * 100}%` }}
            />
          </div>
          <figcaption className="mt-1 text-[12px] text-muted">{FLAGGED_WHEN_TEXT[m.flaggedWhen]}.</figcaption>
        </figure>
      )}
      {!canDraw && <p className="mt-4 text-[12px] text-muted">{FLAGGED_WHEN_TEXT[m.flaggedWhen]}. The two values use different units, so they are not drawn on one scale.</p>}
    </div>
  );
}

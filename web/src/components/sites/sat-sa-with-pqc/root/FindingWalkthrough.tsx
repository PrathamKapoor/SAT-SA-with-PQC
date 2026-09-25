"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { findingWalkthroughContent } from "./content/demo";

type TabId = "why" | "evidence" | "recommendation" | "trust";

const TABS: { id: TabId; label: string }[] = [
  { id: "why", label: "01 · Why" },
  { id: "evidence", label: "02 · Evidence" },
  { id: "recommendation", label: "03 · Recommendation" },
  { id: "trust", label: "04 · Trust" },
];

interface FindingWalkthroughProps {
  content: typeof findingWalkthroughContent;
}

/**
 * "An actual working of it": a click-through of one real finding, exactly as the live product
 * shows it. Every string here is copied from the finding-detail page; this is not a simulation
 * of the product, it's the product's own explanation, made explorable.
 */
export function FindingWalkthrough({ content }: FindingWalkthroughProps) {
  const [tab, setTab] = useState<TabId>("why");

  return (
    <div className="overflow-hidden rounded-8 border border-white/10 bg-[#0a0a0a]">
      {/* Header: mirrors the live finding-detail page's title block */}
      <div className="flex flex-col gap-16 border-white/10 border-b px-16 py-20 sm:flex-row sm:items-start sm:justify-between lg:px-32 lg:py-32">
        <div>
          <span className="mb-12 inline-block rounded-2 border border-[#7c3aed]/30 bg-[#7c3aed]/10 px-8 py-2 font-mono text-ui text-[#7c3aed] uppercase">
            {content.state}
          </span>
          <h3 className="mb-8 max-w-500 text-balance font-medium text-headline-10 text-white">{content.title}</h3>
          <p className="font-mono text-ui text-dark-grey">
            {content.entity} &middot; {content.rule}
          </p>
        </div>
        <div className="grid grid-cols-2 gap-x-24 gap-y-8 sm:text-right">
          <Stat label="Confidence" value={`${content.confidence}%`} />
          <Stat label="Evidence" value={String(content.evidenceCount)} />
          <Stat label="Reviews" value={String(content.reviewCount)} />
          <Stat label="Trust" value={content.trust} />
        </div>
      </div>

      <p className="border-white/10 border-b px-16 py-16 text-body-10 text-ghost-grey lg:px-32">{content.rationale}</p>

      {/* Tabs */}
      <div className="flex flex-wrap gap-4 border-white/10 border-b px-16 py-8 lg:px-32" role="tablist" aria-label="Finding sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={cn(
              "rounded-4 px-12 py-8 font-mono text-ui uppercase transition-colors",
              tab === t.id ? "bg-white/10 text-white" : "text-dark-grey hover:text-white",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Panel */}
      <div className="px-16 py-20 lg:px-32 lg:py-32">
        {tab === "why" ? (
          <div>
            <p className="mb-16 text-body-10 text-dark-grey">{content.why.intro}</p>
            <dl className="flex flex-col divide-y divide-white/10 border-white/10 border-t">
              {content.why.rows.map((row) => (
                <div key={row.field} className="flex items-center justify-between gap-16 py-10 font-mono text-ui uppercase">
                  <dt className="text-dark-grey">{row.field}</dt>
                  <dd className="tabular-nums text-white">{row.value}</dd>
                </div>
              ))}
            </dl>
          </div>
        ) : null}

        {tab === "evidence" ? (
          <div>
            <p className="mb-16 text-body-10 text-dark-grey">{content.evidence.intro}</p>
            <div className="overflow-x-auto">
              <table className="w-full min-w-500 border-collapse font-mono text-ui uppercase">
                <thead>
                  <tr className="border-white/10 border-b text-dark-grey">
                    <th className="py-8 text-left font-normal">Source record</th>
                    <th className="py-8 text-left font-normal">Submission</th>
                    <th className="py-8 text-left font-normal">Format</th>
                    <th className="py-8 text-left font-normal">Locator</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {content.evidence.rows.map((row) => (
                    <tr key={row.record}>
                      <td className="py-8 text-white">{row.record}</td>
                      <td className="py-8 text-dark-grey">{row.submission}</td>
                      <td className="py-8 text-dark-grey">{row.format}</td>
                      <td className="py-8 text-dark-grey">{row.locator}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}

        {tab === "recommendation" ? (
          <div className="rounded-4 border border-[#7c3aed]/20 bg-[#7c3aed]/[0.04] p-16 lg:p-24">
            <p className="mb-8 font-mono text-caption-10 text-[#7c3aed] uppercase">{content.recommendation.action}</p>
            <p className="mb-12 text-body-10 text-white">{content.recommendation.detail}</p>
            <p className="text-ui text-dark-grey italic">{content.recommendation.caveat}</p>
          </div>
        ) : null}

        {tab === "trust" ? (
          <div className="flex flex-col gap-16">
            <div className="flex items-center gap-8 font-mono text-caption-10 text-[#7c3aed] uppercase">
              <span aria-hidden="true" className="size-8 rounded-full bg-[#7c3aed]" />
              {content.trust} signed
            </div>
            <div>
              <p className="mb-4 font-mono text-ui text-dark-grey uppercase">Review history</p>
              <p className="text-body-10 text-white">{content.reviewHistory}</p>
            </div>
            <div>
              <p className="mb-4 font-mono text-ui text-dark-grey uppercase">What this finding cannot tell you</p>
              <p className="text-body-10 text-dark-grey">{content.limitation}</p>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="font-medium text-white">{value}</div>
      <div className="font-mono text-ui text-dark-grey uppercase">{label}</div>
    </div>
  );
}

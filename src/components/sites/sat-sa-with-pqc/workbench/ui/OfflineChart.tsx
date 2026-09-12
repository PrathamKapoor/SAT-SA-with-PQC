"use client";

import React, { useState } from "react";
import { TimeSeriesPoint } from "../data/trends";

interface LineSeriesProps {
  data: TimeSeriesPoint[];
  metricKey1: "csexValue" | "cseyValue";
  metricLabel1: string;
  metricColor1?: string;
  metricKey2?: "cohortMedian";
  metricLabel2?: string;
  metricColor2?: string;
  baselineKey?: "sectorBaseline";
  baselineLabel?: string;
  yUnit?: string;
  height?: number;
}

export const OfflineLineChart: React.FC<LineSeriesProps> = ({
  data,
  metricKey1,
  metricLabel1,
  metricColor1 = "#f59e0b", // Amber
  metricKey2 = "cohortMedian",
  metricLabel2 = "Cohort Median",
  metricColor2 = "#3b82f6", // Blue
  baselineKey = "sectorBaseline",
  baselineLabel = "Sector Baseline",
  yUnit = "",
  height = 240,
}) => {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const width = 600;
  const padding = { top: 20, right: 30, bottom: 35, left: 45 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  // Find min and max
  const allValues = data.flatMap((d) => [
    d[metricKey1],
    metricKey2 ? d[metricKey2] : 0,
    baselineKey ? d[baselineKey] : 0,
  ]);
  const minVal = Math.floor(Math.min(...allValues) * 0.85);
  const maxVal = Math.ceil(Math.max(...allValues) * 1.15) || 10;

  const getX = (idx: number) => padding.left + (idx / (data.length - 1)) * chartWidth;
  const getY = (val: number) => padding.top + chartHeight - ((val - minVal) / (maxVal - minVal)) * chartHeight;

  const path1 = data
    .map((d, i) => `${i === 0 ? "M" : "L"} ${getX(i)} ${getY(d[metricKey1])}`)
    .join(" ");

  const path2 = metricKey2
    ? data.map((d, i) => `${i === 0 ? "M" : "L"} ${getX(i)} ${getY(d[metricKey2])}`).join(" ")
    : "";

  const pathBaseline = baselineKey
    ? data.map((d, i) => `${i === 0 ? "M" : "L"} ${getX(i)} ${getY(d[baselineKey])}`).join(" ")
    : "";

  // Y-axis ticks
  const yTicks = [minVal, Math.round((minVal + maxVal) / 2), maxVal];

  return (
    <div className="w-full">
      {/* Legend */}
      <div className="mb-3 flex flex-wrap items-center gap-4 text-xs font-mono text-slate-300">
        <div className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-5 rounded" style={{ backgroundColor: metricColor1 }} />
          <span>{metricLabel1}</span>
        </div>
        {metricKey2 && (
          <div className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-5 rounded" style={{ backgroundColor: metricColor2 }} />
            <span>{metricLabel2}</span>
          </div>
        )}
        {baselineKey && (
          <div className="flex items-center gap-1.5">
            <span className="inline-block h-1 w-5 border-t-2 border-dashed border-slate-500" />
            <span className="text-slate-400">{baselineLabel}</span>
          </div>
        )}
      </div>

      <div className="relative overflow-hidden rounded border border-slate-800 bg-slate-900/60 p-2">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto" preserveAspectRatio="xMidYMid meet">
          {/* Horizontal Grid Lines */}
          {yTicks.map((tick, i) => {
            const y = getY(tick);
            return (
              <g key={i}>
                <line
                  x1={padding.left}
                  y1={y}
                  x2={width - padding.right}
                  y2={y}
                  stroke="#1e293b"
                  strokeDasharray="3 3"
                />
                <text
                  x={padding.left - 8}
                  y={y + 4}
                  textAnchor="end"
                  fill="#64748b"
                  className="font-mono text-[10px]"
                >
                  {tick}
                  {yUnit}
                </text>
              </g>
            );
          })}

          {/* Baseline Curve */}
          {pathBaseline && (
            <path
              d={pathBaseline}
              fill="none"
              stroke="#64748b"
              strokeWidth="1.5"
              strokeDasharray="4 4"
            />
          )}

          {/* Cohort Median Curve */}
          {path2 && (
            <path
              d={path2}
              fill="none"
              stroke={metricColor2}
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Entity Curve */}
          <path
            d={path1}
            fill="none"
            stroke={metricColor1}
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Data Points */}
          {data.map((d, i) => {
            const x = getX(i);
            const y1 = getY(d[metricKey1]);
            const isHovered = hoverIndex === i;

            return (
              <g key={i}>
                {/* Vertical hover guide */}
                {isHovered && (
                  <line
                    x1={x}
                    y1={padding.top}
                    x2={x}
                    y2={height - padding.bottom}
                    stroke="#475569"
                    strokeWidth="1"
                    strokeDasharray="2 2"
                  />
                )}

                {/* Point dot 1 */}
                <circle
                  cx={x}
                  cy={y1}
                  r={isHovered ? 5 : 3.5}
                  fill={metricColor1}
                  stroke="#0f172a"
                  strokeWidth="2"
                  className="cursor-pointer transition-all"
                  onMouseEnter={() => setHoverIndex(i)}
                  onMouseLeave={() => setHoverIndex(null)}
                />

                {/* X-axis labels */}
                <text
                  x={x}
                  y={height - padding.bottom + 18}
                  textAnchor="middle"
                  fill={isHovered ? "#f8fafc" : "#64748b"}
                  className="font-mono text-[10px] select-none"
                >
                  {d.period.split(" ")[0]}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Hover Tooltip Box */}
        {hoverIndex !== null && (
          <div className="absolute top-3 right-3 rounded border border-slate-700 bg-slate-950/90 px-2.5 py-1.5 text-xs font-mono shadow-md backdrop-blur">
            <div className="text-slate-400 font-semibold border-b border-slate-800 pb-1 mb-1">
              {data[hoverIndex].period}
            </div>
            <div className="flex items-center justify-between gap-4 text-amber-300">
              <span>{metricLabel1}:</span>
              <span className="font-bold">
                {data[hoverIndex][metricKey1]}
                {yUnit}
              </span>
            </div>
            {metricKey2 && (
              <div className="flex items-center justify-between gap-4 text-blue-300">
                <span>{metricLabel2}:</span>
                <span>
                  {data[hoverIndex][metricKey2]}
                  {yUnit}
                </span>
              </div>
            )}
            {baselineKey && (
              <div className="flex items-center justify-between gap-4 text-slate-400">
                <span>{baselineLabel}:</span>
                <span>
                  {data[hoverIndex][baselineKey]}
                  {yUnit}
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export const OfflineBarChart: React.FC<{
  data: { label: string; value: number; benchmark: number; status?: string }[];
  yUnit?: string;
}> = ({ data, yUnit = "%" }) => {
  return (
    <div className="space-y-3">
      {data.map((item, i) => {
        const isLow = item.value < item.benchmark * 0.7;
        const isAttention = item.value < item.benchmark && !isLow;

        return (
          <div key={i} className="space-y-1">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-slate-300">{item.label}</span>
              <div className="flex items-center gap-3">
                <span className="text-slate-500">Benchmark: {item.benchmark}{yUnit}</span>
                <span
                  className={`font-semibold ${
                    isLow ? "text-red-400" : isAttention ? "text-amber-400" : "text-emerald-400"
                  }`}
                >
                  {item.value}{yUnit}
                </span>
              </div>
            </div>

            <div className="relative h-2.5 w-full overflow-hidden rounded bg-slate-800">
              {/* Benchmark marker line */}
              <div
                className="absolute top-0 bottom-0 z-10 w-0.5 bg-slate-400"
                style={{ left: `${Math.min(100, item.benchmark)}%` }}
              />
              {/* Actual bar */}
              <div
                className={`h-full rounded transition-all duration-300 ${
                  isLow ? "bg-red-500" : isAttention ? "bg-amber-500" : "bg-emerald-500"
                }`}
                style={{ width: `${Math.min(100, item.value)}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
};

"use client";

import React, { useState, useMemo } from "react";
import Link from "next/link";
import {
  Search,
  Filter,
  ArrowUpDown,
  ArrowUpRight,
  TrendingUp,
  TrendingDown,
  Minus,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ShieldCheck,
} from "lucide-react";
import { useWorkbench } from "@/components/sites/sat-sa-with-pqc/workbench/state/WorkbenchContext";
import { StatusBadge } from "@/components/sites/sat-sa-with-pqc/workbench/ui/StatusBadge";
import { Entity } from "@/components/sites/sat-sa-with-pqc/workbench/data/entities";

type SortField = "score" | "name" | "sector" | "completeness" | "findings";

export default function EntitiesPage() {
  const { entitiesList, selectedCohort } = useWorkbench();
  const [searchQuery, setSearchQuery] = useState("");
  const [sectorFilter, setSectorFilter] = useState("All");
  const [riskFilter, setRiskFilter] = useState("All");
  const [sortField, setSortField] = useState<SortField>("score");
  const [sortAsc, setSortAsc] = useState(false);

  // Sectors list
  const sectors = ["All", "Banking", "Defence", "Energy & Power", "Telecom", "Transport & Civil Aviation", "Government"];

  // Filtered and sorted
  const filtered = useMemo(() => {
    return entitiesList
      .filter((e) => {
        if (selectedCohort !== "All Cohorts" && e.cohort !== selectedCohort) return false;
        if (sectorFilter !== "All" && e.sector !== sectorFilter) return false;
        if (riskFilter !== "All" && e.band !== riskFilter.toLowerCase()) return false;
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          return (
            e.name.toLowerCase().includes(q) ||
            e.slug.toLowerCase().includes(q) ||
            e.sector.toLowerCase().includes(q)
          );
        }
        return true;
      })
      .sort((a, b) => {
        let cmp = 0;
        if (sortField === "score") cmp = b.score - a.score;
        else if (sortField === "name") cmp = a.name.localeCompare(b.name);
        else if (sortField === "sector") cmp = a.sector.localeCompare(b.sector);
        else if (sortField === "completeness") cmp = b.dataCompletenessPct - a.dataCompletenessPct;
        else if (sortField === "findings") cmp = b.findings - a.findings;
        return sortAsc ? -cmp : cmp;
      });
  }, [entitiesList, selectedCohort, sectorFilter, riskFilter, searchQuery, sortField, sortAsc]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white">
            Constituent Security Entities (CSEs)
          </h1>
          <p className="text-xs font-mono text-slate-400 mt-0.5">
            Sortable supervisory risk directory · Total: {filtered.length} matching entities
          </p>
        </div>
      </div>

      {/* Filter and Search Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-800 bg-[#0c1424] p-3 text-xs font-mono">
        <div className="flex flex-wrap items-center gap-2.5 flex-1 min-w-[280px]">
          {/* Search box */}
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-2.5 top-2.5 size-3.5 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by entity name or code (e.g. CSE-X)..."
              className="w-full rounded border border-slate-700 bg-slate-950 py-1.5 pl-8 pr-3 text-xs text-slate-200 placeholder:text-slate-500 focus:border-blue-500 focus:outline-none"
            />
          </div>

          {/* Sector filter */}
          <div className="flex items-center gap-1.5">
            <span className="text-slate-400 text-[11px] uppercase">Sector:</span>
            <select
              aria-label="Filter by Sector"
              value={sectorFilter}
              onChange={(e) => setSectorFilter(e.target.value)}
              className="rounded border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none"
            >
              {sectors.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

          {/* Risk Band filter */}
          <div className="flex items-center gap-1.5">
            <span className="text-slate-400 text-[11px] uppercase">Risk:</span>
            <select
              aria-label="Filter by Risk Band"
              value={riskFilter}
              onChange={(e) => setRiskFilter(e.target.value)}
              className="rounded border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none"
            >
              <option value="All">All Risks</option>
              <option value="High">High (&gt;60)</option>
              <option value="Medium">Medium (35–60)</option>
              <option value="Low">Low (&lt;35)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Sortable Table */}
      <div className="rounded-lg border border-slate-800 bg-[#0c1424] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-900/80 font-mono text-[11px] text-slate-400 uppercase tracking-wider">
                <th
                  onClick={() => handleSort("name")}
                  className="py-3 px-4 cursor-pointer hover:text-white"
                >
                  <div className="flex items-center gap-1">
                    <span>Entity & Sector</span>
                    <ArrowUpDown className="size-3" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort("score")}
                  className="py-3 px-3 cursor-pointer hover:text-white"
                >
                  <div className="flex items-center gap-1">
                    <span>Supervisory Risk</span>
                    <ArrowUpDown className="size-3" />
                  </div>
                </th>
                <th className="py-3 px-3">Trend</th>
                <th
                  onClick={() => handleSort("completeness")}
                  className="py-3 px-3 cursor-pointer hover:text-white"
                >
                  <div className="flex items-center gap-1">
                    <span>Completeness</span>
                    <ArrowUpDown className="size-3" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort("findings")}
                  className="py-3 px-3 cursor-pointer hover:text-white text-center"
                >
                  <div className="flex items-center justify-center gap-1">
                    <span>High Findings</span>
                    <ArrowUpDown className="size-3" />
                  </div>
                </th>
                <th className="py-3 px-3">Peer Cohort</th>
                <th className="py-3 px-3">Review Status</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono text-slate-300">
              {filtered.map((entity) => (
                <tr
                  key={entity.slug}
                  className="hover:bg-slate-800/40 transition-colors"
                >
                  {/* Entity name & sector */}
                  <td className="py-3 px-4 font-sans">
                    <Link
                      href={`/workbench/entities/${entity.slug}`}
                      className="font-semibold text-sm text-slate-100 hover:text-blue-400 transition-colors block"
                    >
                      {entity.name}
                    </Link>
                    <span className="font-mono text-[11px] text-slate-400">
                      {entity.sector} · {entity.environment}
                    </span>
                  </td>

                  {/* Overall Risk Score */}
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-sm text-white">
                        {entity.score.toFixed(1)} <span className="text-slate-500 font-normal text-[11px]">/ 100</span>
                      </span>
                      <StatusBadge
                        variant={
                          entity.band === "high"
                            ? "attention"
                            : entity.band === "medium"
                            ? "navigational"
                            : "verified"
                        }
                        label={entity.band.toUpperCase()}
                        size="sm"
                      />
                    </div>
                  </td>

                  {/* Trend */}
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-1 text-[11px]">
                      {entity.trend === "deteriorating" && (
                        <>
                          <TrendingUp className="size-3.5 text-red-400" />
                          <span className="text-red-400 font-semibold">
                            +{entity.trendDelta} pts
                          </span>
                        </>
                      )}
                      {entity.trend === "stable" && (
                        <>
                          <Minus className="size-3.5 text-slate-400" />
                          <span className="text-slate-400">Stable</span>
                        </>
                      )}
                      {entity.trend === "improving" && (
                        <>
                          <TrendingDown className="size-3.5 text-emerald-400" />
                          <span className="text-emerald-400 font-semibold">
                            {entity.trendDelta} pts
                          </span>
                        </>
                      )}
                    </div>
                  </td>

                  {/* Completeness / Confidence */}
                  <td className="py-3 px-3">
                    <div className="flex flex-col gap-1">
                      <div className="flex items-center justify-between text-[10px]">
                        <span>{entity.dataCompletenessPct}%</span>
                        <span className="uppercase text-slate-400">
                          {entity.confidence} conf
                        </span>
                      </div>
                      <div className="h-1.5 w-24 overflow-hidden rounded bg-slate-800">
                        <div
                          className={`h-full ${
                            entity.dataCompletenessPct >= 90
                              ? "bg-emerald-500"
                              : entity.dataCompletenessPct >= 80
                              ? "bg-amber-500"
                              : "bg-red-500"
                          }`}
                          style={{ width: `${entity.dataCompletenessPct}%` }}
                        />
                      </div>
                    </div>
                  </td>

                  {/* Open High Findings */}
                  <td className="py-3 px-3 text-center">
                    {entity.openHighPriorityFindings > 0 ? (
                      <span className="inline-block rounded bg-amber-500/15 border border-amber-500/30 px-2 py-0.5 font-bold text-amber-300">
                        {entity.openHighPriorityFindings}
                      </span>
                    ) : (
                      <span className="text-slate-500">0</span>
                    )}
                  </td>

                  {/* Peer Cohort */}
                  <td className="py-3 px-3 text-slate-400 font-sans text-[11px]">
                    {entity.cohort}
                  </td>

                  {/* Review Status */}
                  <td className="py-3 px-3">
                    <span
                      className={`inline-block rounded px-2 py-0.5 text-[10px] uppercase font-semibold ${
                        entity.reviewStatus === "open"
                          ? "bg-amber-500/10 text-amber-300 border border-amber-500/20"
                          : entity.reviewStatus === "in_review"
                          ? "bg-blue-500/10 text-blue-300 border border-blue-500/20"
                          : "bg-slate-800 text-slate-400"
                      }`}
                    >
                      {entity.reviewStatus.replace(/_/g, " ")}
                    </span>
                  </td>

                  {/* Action Link */}
                  <td className="py-3 px-4 text-right">
                    <Link
                      href={`/workbench/entities/${entity.slug}`}
                      className="inline-flex items-center gap-1 rounded border border-slate-700 bg-slate-800/80 px-2.5 py-1 text-[11px] font-medium text-blue-300 hover:bg-slate-700 transition-colors"
                    >
                      <span>Profile</span>
                      <ArrowUpRight className="size-3" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

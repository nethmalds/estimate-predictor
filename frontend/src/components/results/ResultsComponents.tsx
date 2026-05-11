"use client";

import { useState, useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import { Download, ChevronUp, ChevronDown, AlertTriangle } from "lucide-react";
import * as XLSX from "xlsx";

interface BoqItem {
  description?: string;
  bsr_description?: string;
  section?: string;
  category?: string;
  unit?: string;
  quantity?: number;
  rate?: number;
  cost?: number;
  bsr_item_no?: string;
  match_type?: string;
  match_confidence?: number;
  quantity_source?: string;
  needs_rate_review?: boolean;
}

interface CostBreakdownProps {
  subtotals: Record<string, number>;
}

const CHART_COLORS = [
  "#3b82f6","#10b981","#f59e0b","#ef4444","#8b5cf6",
  "#06b6d4","#ec4899","#84cc16","#f97316","#6366f1",
];

function CostBreakdownChart({ subtotals }: CostBreakdownProps) {
  const data = Object.entries(subtotals)
    .sort(([, a], [, b]) => b - a)
    .map(([key, value]) => ({
      name: key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      value,
    }));

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 mb-6">
      <h2 className="font-semibold text-zinc-100 mb-4">Cost Breakdown by Category</h2>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data} margin={{ top: 4, right: 16, left: 8, bottom: 60 }}>
          <XAxis
            dataKey="name"
            tick={{ fill: "#a1a1aa", fontSize: 10 }}
            angle={-35}
            textAnchor="end"
            interval={0}
          />
          <YAxis
            tick={{ fill: "#a1a1aa", fontSize: 10 }}
            tickFormatter={(v) => `${(v / 1_000_000).toFixed(1)}M`}
          />
          <Tooltip
            formatter={(v) => [`LKR ${Number(v ?? 0).toLocaleString()}`, "Cost"]}
            contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", borderRadius: 8 }}
            labelStyle={{ color: "#e4e4e7" }}
          />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {data.map((_, i) => (
              <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

interface ConfidenceBreakdownProps {
  confidence: Record<string, unknown>;
}

function ConfidenceBreakdownCard({ confidence }: ConfidenceBreakdownProps) {
  const score = Number(confidence.score ?? 0);
  const breakdown = (confidence.breakdown as Record<string, number>) ?? {};
  const sectionBreakdown = (confidence.section_breakdown as Record<string, number>) ?? {};

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 mb-6">
      <h2 className="font-semibold text-zinc-100 mb-4">
        Confidence Score — {(score * 100).toFixed(1)}%
      </h2>
      {Object.keys(breakdown).length > 0 && (
        <div className="mb-4 space-y-1">
          {Object.entries(breakdown).map(([k, v]) => (
            <div key={k} className="flex justify-between text-xs">
              <span className="text-zinc-400">{k.replace(/_/g, " ")}</span>
              <span className={v >= 0 ? "text-green-400" : "text-red-400"}>
                {v >= 0 ? "+" : ""}{(v * 100).toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
      )}
      {Object.keys(sectionBreakdown).length > 0 && (
        <>
          <p className="text-xs text-zinc-500 uppercase tracking-wide mb-2">Section confidence</p>
          <div className="space-y-1">
            {Object.entries(sectionBreakdown).map(([section, score]) => (
              <div key={section} className="flex justify-between text-xs">
                <span className="text-zinc-400">{section.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}</span>
                <span className={Number(score) >= 0.6 ? "text-green-400" : "text-yellow-400"}>
                  {(Number(score) * 100).toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

type SortKey = "description" | "section" | "quantity" | "rate" | "cost";

function SortIcon({ col, sortKey, sortAsc }: { col: SortKey; sortKey: SortKey; sortAsc: boolean }) {
  return sortKey === col ? (sortAsc ? <ChevronUp className="w-3 h-3 inline" /> : <ChevronDown className="w-3 h-3 inline" />) : null;
}

interface FullBoqTableProps {
  items: BoqItem[];
  grandTotal: number;
}

function FullBoqTable({ items, grandTotal }: FullBoqTableProps) {
  const [filter, setFilter] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("section");
  const [sortAsc, setSortAsc] = useState(true);
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 25;

  const filtered = useMemo(() => {
    const q = filter.toLowerCase();
    return items.filter((it) =>
      !q ||
      (it.description ?? it.bsr_description ?? "").toLowerCase().includes(q) ||
      (it.section ?? it.category ?? "").toLowerCase().includes(q)
    );
  }, [items, filter]);

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      let av: string | number = "";
      let bv: string | number = "";
      if (sortKey === "description") { av = a.description ?? a.bsr_description ?? ""; bv = b.description ?? b.bsr_description ?? ""; }
      else if (sortKey === "section") { av = a.section ?? a.category ?? ""; bv = b.section ?? b.category ?? ""; }
      else if (sortKey === "quantity") { av = a.quantity ?? 0; bv = b.quantity ?? 0; }
      else if (sortKey === "rate") { av = a.rate ?? 0; bv = b.rate ?? 0; }
      else if (sortKey === "cost") { av = a.cost ?? 0; bv = b.cost ?? 0; }
      if (typeof av === "string") return sortAsc ? av.localeCompare(bv as string) : (bv as string).localeCompare(av);
      return sortAsc ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
  }, [filtered, sortKey, sortAsc]);

  const totalPages = Math.ceil(sorted.length / PAGE_SIZE);
  const pageItems = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const handleSort = (key: SortKey) => {
    if (key === sortKey) setSortAsc((a) => !a);
    else { setSortKey(key); setSortAsc(true); }
    setPage(1);
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl mb-6">
      <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between gap-4">
        <h2 className="font-semibold text-zinc-100 shrink-0">Bill of Quantities ({items.length} items)</h2>
        <input
          type="text"
          placeholder="Filter by description or section..."
          value={filter}
          onChange={(e) => { setFilter(e.target.value); setPage(1); }}
          className="flex-1 max-w-xs bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-1.5 text-xs text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="bg-zinc-800 text-zinc-400">
            <tr>
              <th className="px-3 py-2 text-left w-8">#</th>
              <th className="px-3 py-2 text-left cursor-pointer select-none" onClick={() => handleSort("section")}>
                Section <SortIcon col="section" sortKey={sortKey} sortAsc={sortAsc} />
              </th>
              <th className="px-3 py-2 text-left cursor-pointer select-none" onClick={() => handleSort("description")}>
                Description <SortIcon col="description" sortKey={sortKey} sortAsc={sortAsc} />
              </th>
              <th className="px-3 py-2 text-right">Unit</th>
              <th className="px-3 py-2 text-right cursor-pointer select-none" onClick={() => handleSort("quantity")}>
                Qty <SortIcon col="quantity" sortKey={sortKey} sortAsc={sortAsc} />
              </th>
              <th className="px-3 py-2 text-right cursor-pointer select-none" onClick={() => handleSort("rate")}>
                Rate (LKR) <SortIcon col="rate" sortKey={sortKey} sortAsc={sortAsc} />
              </th>
              <th className="px-3 py-2 text-right cursor-pointer select-none" onClick={() => handleSort("cost")}>
                Cost (LKR) <SortIcon col="cost" sortKey={sortKey} sortAsc={sortAsc} />
              </th>
              <th className="px-3 py-2 text-right">Match</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800">
            {pageItems.map((item, i) => {
              const isNoMatch = item.match_type === "no_match";
              const needsReview = item.needs_rate_review;
              const rowClass = isNoMatch
                ? "bg-red-950/20 text-zinc-300"
                : needsReview
                ? "bg-yellow-950/20 text-zinc-300"
                : "text-zinc-300";
              return (
                <tr key={i} className={rowClass}>
                  <td className="px-3 py-2 text-zinc-500">{(page - 1) * PAGE_SIZE + i + 1}</td>
                  <td className="px-3 py-2 text-zinc-400 whitespace-nowrap">
                    {(item.section ?? item.category ?? "—").replace(/_/g, " ").slice(0, 28)}
                  </td>
                  <td className="px-3 py-2 max-w-xs">
                    <span className="flex items-start gap-1">
                      {(isNoMatch || needsReview) && (
                        <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0 text-yellow-400" />
                      )}
                      {item.description ?? item.bsr_description ?? "—"}
                    </span>
                    {item.bsr_item_no && (
                      <span className="text-zinc-600 text-[10px]">{item.bsr_item_no}</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right">{item.unit ?? "—"}</td>
                  <td className="px-3 py-2 text-right">{item.quantity?.toFixed(2) ?? "—"}</td>
                  <td className="px-3 py-2 text-right">{item.rate?.toLocaleString() ?? "—"}</td>
                  <td className="px-3 py-2 text-right font-medium">{item.cost?.toLocaleString() ?? "—"}</td>
                  <td className="px-3 py-2 text-right">
                    <span className={`text-[10px] rounded-full px-1.5 py-0.5 border ${
                      item.match_type === "confirmed" ? "bg-green-500/10 text-green-400 border-green-500/20" :
                      item.match_type === "contractual" ? "bg-zinc-700 text-zinc-400 border-zinc-600" :
                      item.match_type === "soft_match" ? "bg-yellow-500/10 text-yellow-400 border-yellow-500/20" :
                      "bg-red-500/10 text-red-400 border-red-500/20"
                    }`}>
                      {item.match_type === "confirmed" && item.match_confidence != null
                        ? `${(item.match_confidence * 100).toFixed(0)}%`
                        : (item.match_type ?? "—")}
                    </span>
                  </td>
                </tr>
              );
            })}
            {/* Grand total footer */}
            {page === totalPages && (
              <tr className="bg-zinc-800 font-semibold text-zinc-200">
                <td colSpan={6} className="px-3 py-2">Grand Total (incl. contingencies)</td>
                <td className="px-3 py-2 text-right">LKR {grandTotal.toLocaleString()}</td>
                <td></td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <div className="px-6 py-3 border-t border-zinc-800 flex items-center justify-between text-xs text-zinc-500">
          <span>{filtered.length} items, page {page} of {totalPages}</span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 disabled:opacity-40 rounded"
            >
              Prev
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 disabled:opacity-40 rounded"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export { CostBreakdownChart, ConfidenceBreakdownCard, FullBoqTable };
export type { BoqItem };

// ── Client-side Excel generator (extended with Audit sheet) ────────────────
export function generateExcelReport(data: Record<string, unknown>): ArrayBuffer {
  const wb = XLSX.utils.book_new();
  const projectInfo = (data.project_info as Record<string, unknown>) ?? {};
  const parameters  = (projectInfo.parameters as Record<string, unknown>) ?? {};
  const costs       = (data.costs as Record<string, unknown>) ?? {};
  const confidence  = (data.confidence as Record<string, unknown>) ?? {};
  const boqItems    = (data.boq_items as Record<string, unknown>[]) ?? [];

  // Summary
  const summaryRows: unknown[][] = [
    ["CONSTRUCTION COST ESTIMATION REPORT"], [],
    ["PROJECT DETAILS", ""],
    ["Building Type",    projectInfo.building_type ?? "—"],
    ["Number of Floors", projectInfo.floors ?? "—"],
    ["Built-up Area",    parameters.built_up_area ?? "—"],
    ["Finish Level",     parameters.finish_level ?? "—"],
    ["Roof Type",        parameters.roof_type ?? "—"],
    ["Ceiling Type",     parameters.ceiling_type ?? "—"],
    ["Location",         parameters.location ?? "—"],
    [],
    ["COST SUMMARY", ""],
    ["Base Total (LKR)",           costs.base_total ?? 0],
    ["External Works Total (LKR)", costs.external_works_total ?? 0],
    ["Preliminaries",              costs.preliminaries ?? 0],
    ["Contingencies",              costs.contingencies ?? 0],
    ["Grand Total (LKR)",          costs.total ?? 0],
    [],
    ["ESTIMATE QUALITY", ""],
    ["Confidence Score", String(((Number((confidence as Record<string,unknown>).score) || 0) * 100).toFixed(1)) + "%"],
    ["Total BOQ Items",  boqItems.length],
  ];
  const summarySheet = XLSX.utils.aoa_to_sheet(summaryRows);
  summarySheet["!cols"] = [{ wch: 30 }, { wch: 42 }];
  XLSX.utils.book_append_sheet(wb, summarySheet, "Summary");

  // BOQ
  const boqHeaders = ["No.","Description","Category","Unit","Quantity","Rate (LKR)","Cost (LKR)","BSR Code","Match %"];
  const boqRows: unknown[][] = [boqHeaders];
  for (let i = 0; i < boqItems.length; i++) {
    const item = boqItems[i];
    const conf = item.match_confidence as number | undefined;
    boqRows.push([
      i + 1,
      item.description || item.bsr_description || "—",
      item.section || item.category || "Uncategorized",
      item.unit || "—",
      item.quantity ?? 0,
      item.rate ?? 0,
      item.cost ?? 0,
      item.bsr_item_no || "—",
      conf != null ? String((conf * 100).toFixed(0)) + "%" : "—",
    ]);
  }
  boqRows.push([]);
  boqRows.push(["","","","","","GRAND TOTAL (incl. 5% Contingencies)", costs.total ?? 0,"",""]);
  const boqSheet = XLSX.utils.aoa_to_sheet(boqRows);
  boqSheet["!cols"] = [{wch:6},{wch:48},{wch:26},{wch:10},{wch:12},{wch:16},{wch:16},{wch:18},{wch:10}];
  boqSheet["!freeze"] = { xSplit: 0, ySplit: 1 };
  XLSX.utils.book_append_sheet(wb, boqSheet, "Bill of Quantities");

  // Cost Breakdown
  const subtotals = (costs.subtotals as Record<string, number>) ?? {};
  const baseTotal = (costs.base_total as number) || 1;
  const breakdownRows: unknown[][] = [["Category","Subtotal (LKR)","% of Base Total"]];
  Object.entries(subtotals).sort(([,a],[,b]) => b-a).forEach(([cat, amount]) => {
    breakdownRows.push([cat.replace(/_/g," ").replace(/\b\w/g,(c)=>c.toUpperCase()), amount, String(((amount/baseTotal)*100).toFixed(1))+"%"]);
  });
  breakdownRows.push([]);
  breakdownRows.push(["Base Total", costs.base_total ?? 0, "100%"]);
  breakdownRows.push(["External Works Subtotal", costs.external_works_total ?? 0, ""]);
  breakdownRows.push(["Preliminaries", costs.preliminaries ?? 0, ""]);
  breakdownRows.push(["Contingencies", costs.contingencies ?? 0, ""]);
  breakdownRows.push(["Grand Total", costs.total ?? 0, ""]);
  const breakdownSheet = XLSX.utils.aoa_to_sheet(breakdownRows);
  breakdownSheet["!cols"] = [{wch:36},{wch:20},{wch:16}];
  XLSX.utils.book_append_sheet(wb, breakdownSheet, "Cost Breakdown");

  // Audit sheet (IMP-REP-01)
  const auditHeaders = ["No.","Description","Match Type","Match Confidence","Qty Source","Qty Confidence","Needs Rate Review","Warnings"];
  const auditRows: unknown[][] = [auditHeaders];
  for (let i = 0; i < boqItems.length; i++) {
    const item = boqItems[i];
    auditRows.push([
      i + 1,
      item.description || item.bsr_description || "—",
      item.match_type || "—",
      item.match_confidence != null ? String(((item.match_confidence as number)*100).toFixed(0))+"%": "—",
      item.quantity_source || "—",
      item.quantity_confidence_score != null ? String(((item.quantity_confidence_score as number)*100).toFixed(0))+"%": "—",
      item.needs_rate_review ? "YES" : "no",
      (item.warnings as string[] | undefined)?.join("; ") ?? "",
    ]);
  }
  const auditSheet = XLSX.utils.aoa_to_sheet(auditRows);
  auditSheet["!cols"] = [{wch:6},{wch:48},{wch:14},{wch:16},{wch:16},{wch:16},{wch:18},{wch:40}];
  auditSheet["!freeze"] = { xSplit: 0, ySplit: 1 };
  XLSX.utils.book_append_sheet(wb, auditSheet, "Audit");

  return XLSX.write(wb, { bookType: "xlsx", type: "array" }) as ArrayBuffer;
}

// ── Download helper (direct Blob URL — no UploadThing required) ────────────
export function downloadExcelBlob(data: Record<string, unknown>): void {
  const buffer = generateExcelReport(data);
  const blob = new Blob([buffer], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "estimate_" + new Date().toISOString().slice(0, 10) + ".xlsx";
  a.click();
  URL.revokeObjectURL(url);
}

interface ResultsActionsProps {
  estimateData: Record<string, unknown>;
  excelUrl: string | null;
  onNewEstimate: () => void;
}

export function ResultsActions({ estimateData, excelUrl, onNewEstimate }: ResultsActionsProps) {
  const handleDownload = () => {
    if (excelUrl) {
      window.open(excelUrl, "_blank");
    } else {
      downloadExcelBlob(estimateData);
    }
  };
  return (
    <div className="flex gap-3">
      <button
        onClick={handleDownload}
        className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
      >
        <Download className="w-4 h-4" /> Download Excel Report
      </button>
      <button
        onClick={onNewEstimate}
        className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-zinc-200 rounded-lg text-sm font-medium transition-colors"
      >
        New Estimate
      </button>
    </div>
  );
}

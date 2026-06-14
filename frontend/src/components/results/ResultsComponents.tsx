"use client";

import { useState, useMemo } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { ChevronUp, ChevronDown, AlertTriangle, Download } from "lucide-react";
import * as XLSX from "xlsx";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

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
  "#3b82f6",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#06b6d4",
  "#ec4899",
  "#84cc16",
  "#f97316",
  "#6366f1",
];

const MATCH_BADGE: Record<string, string> = {
  confirmed: "bg-green-500/10 text-green-400 border-green-500/20",
  contractual: "bg-muted text-muted-foreground border-border",
  soft_match: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  no_match: "bg-red-500/10 text-red-400 border-red-500/20",
};

function CostBreakdownChart({ subtotals }: CostBreakdownProps) {
  const data = Object.entries(subtotals)
    .sort(([, a], [, b]) => b - a)
    .map(([key, value]) => ({
      name: key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      value,
    }));

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle>Cost Breakdown by Category</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data} margin={{ top: 4, right: 16, left: 8, bottom: 60 }}>
            <XAxis
              dataKey="name"
              tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 10 }}
              angle={-35}
              textAnchor="end"
              interval={0}
            />
            <YAxis
              tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 10 }}
              tickFormatter={(v) => `${(v / 1_000_000).toFixed(1)}M`}
            />
            <Tooltip
              formatter={(v) => [`LKR ${Number(v ?? 0).toLocaleString()}`, "Cost"]}
              contentStyle={{
                background: "hsl(var(--card))",
                border: "1px solid hsl(var(--border))",
                borderRadius: 8,
              }}
              labelStyle={{ color: "hsl(var(--card-foreground))" }}
            />
            <Bar dataKey="value" radius={[4, 4, 0, 0]}>
              {data.map((_, i) => (
                <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

interface SectionStats {
  item_count: number;
  matched: number;
  unmatched: number;
  contractual: number;
}

interface ConfidenceBreakdownProps {
  confidence: Record<string, unknown>;
}

function ConfidenceBreakdownCard({ confidence }: ConfidenceBreakdownProps) {
  const score = Number(confidence.score ?? 0);
  const breakdown = (confidence.breakdown as Record<string, number>) ?? {};
  const rawSectionBreakdown = (confidence.section_breakdown as Record<string, SectionStats | number>) ?? {};

  const categoryData = Object.entries(rawSectionBreakdown)
    .map(([k, v]) => ({
      name: k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      items: typeof v === "number" ? v : (v as SectionStats).item_count,
    }))
    .sort((a, b) => b.items - a.items);

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle>Confidence Score — {(score * 100).toFixed(1)}%</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {Object.keys(breakdown).length > 0 && (
          <div className="space-y-1.5">
            {Object.entries(breakdown).map(([k, v]) => (
              <div key={k} className="flex justify-between text-xs">
                <span className="text-muted-foreground">{k.replace(/_/g, " ")}</span>
                <span className={v >= 0 ? "text-green-400" : "text-destructive"}>
                  {v >= 0 ? "+" : ""}
                  {(v * 100).toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        )}
        {categoryData.length > 0 && (
          <div>
            <p className="text-muted-foreground mb-3 text-xs uppercase tracking-wide">
              Items per Category
            </p>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={categoryData} margin={{ top: 4, right: 16, left: 8, bottom: 90 }}>
                <XAxis
                  dataKey="name"
                  tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 10 }}
                  angle={-40}
                  textAnchor="end"
                  interval={0}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 10 }}
                />
                <Tooltip
                  formatter={(v) => [v, "BOQ Items"]}
                  contentStyle={{
                    background: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: 8,
                  }}
                  labelStyle={{ color: "hsl(var(--card-foreground))" }}
                />
                <Bar dataKey="items" radius={[4, 4, 0, 0]}>
                  {categoryData.map((_, i) => (
                    <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

type SortKey = "description" | "section" | "quantity" | "rate" | "cost";

function SortIcon({ col, sortKey, sortAsc }: { col: SortKey; sortKey: SortKey; sortAsc: boolean }) {
  return sortKey === col ? (
    sortAsc ? (
      <ChevronUp className="inline h-3 w-3" />
    ) : (
      <ChevronDown className="inline h-3 w-3" />
    )
  ) : null;
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
    return items.filter(
      (it) =>
        !q ||
        (it.description ?? it.bsr_description ?? "").toLowerCase().includes(q) ||
        (it.section ?? it.category ?? "").toLowerCase().includes(q)
    );
  }, [items, filter]);

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      let av: string | number = "";
      let bv: string | number = "";
      if (sortKey === "description") {
        av = a.description ?? a.bsr_description ?? "";
        bv = b.description ?? b.bsr_description ?? "";
      } else if (sortKey === "section") {
        av = a.section ?? a.category ?? "";
        bv = b.section ?? b.category ?? "";
      } else if (sortKey === "quantity") {
        av = a.quantity ?? 0;
        bv = b.quantity ?? 0;
      } else if (sortKey === "rate") {
        av = a.rate ?? 0;
        bv = b.rate ?? 0;
      } else if (sortKey === "cost") {
        av = a.cost ?? 0;
        bv = b.cost ?? 0;
      }
      if (typeof av === "string")
        return sortAsc ? av.localeCompare(bv as string) : (bv as string).localeCompare(av);
      return sortAsc ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
  }, [filtered, sortKey, sortAsc]);

  const totalPages = Math.ceil(sorted.length / PAGE_SIZE);
  const pageItems = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const handleSort = (key: SortKey) => {
    if (key === sortKey) setSortAsc((a) => !a);
    else {
      setSortKey(key);
      setSortAsc(true);
    }
    setPage(1);
  };

  return (
    <Card className="mb-6">
      <CardHeader className="flex-row items-center justify-between gap-4">
        <CardTitle className="shrink-0">Bill of Quantities ({items.length} items)</CardTitle>
        <Input
          type="text"
          placeholder="Filter by description or section..."
          value={filter}
          onChange={(e) => {
            setFilter(e.target.value);
            setPage(1);
          }}
          className="max-w-xs text-xs"
        />
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-8">#</TableHead>
                <TableHead
                  className="cursor-pointer whitespace-nowrap select-none"
                  onClick={() => handleSort("section")}
                >
                  Section <SortIcon col="section" sortKey={sortKey} sortAsc={sortAsc} />
                </TableHead>
                <TableHead
                  className="cursor-pointer select-none"
                  onClick={() => handleSort("description")}
                >
                  Description <SortIcon col="description" sortKey={sortKey} sortAsc={sortAsc} />
                </TableHead>
                <TableHead className="text-right">Unit</TableHead>
                <TableHead
                  className="cursor-pointer text-right select-none"
                  onClick={() => handleSort("quantity")}
                >
                  Qty <SortIcon col="quantity" sortKey={sortKey} sortAsc={sortAsc} />
                </TableHead>
                <TableHead
                  className="cursor-pointer text-right whitespace-nowrap select-none"
                  onClick={() => handleSort("rate")}
                >
                  Rate (LKR) <SortIcon col="rate" sortKey={sortKey} sortAsc={sortAsc} />
                </TableHead>
                <TableHead
                  className="cursor-pointer text-right whitespace-nowrap select-none"
                  onClick={() => handleSort("cost")}
                >
                  Cost (LKR) <SortIcon col="cost" sortKey={sortKey} sortAsc={sortAsc} />
                </TableHead>
                <TableHead className="text-right">Match</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pageItems.map((item, i) => {
                const isNoMatch = item.match_type === "no_match";
                return (
                  <TableRow
                    key={i}
                    className={
                      isNoMatch ? "bg-destructive/5" : ""
                    }
                  >
                    <TableCell className="text-muted-foreground text-xs">
                      {(page - 1) * PAGE_SIZE + i + 1}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-xs">
                      {(item.section ?? item.category ?? "—").replace(/_/g, " ")}
                    </TableCell>
                    <TableCell className="max-w-xs text-xs">
                      <div className="flex items-start gap-1">
                        {isNoMatch && (
                          <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-destructive" />
                        )}
                        <span className="break-words whitespace-normal">
                          {item.description ?? item.bsr_description ?? "—"}
                        </span>
                      </div>
                      {item.bsr_item_no && (
                        <div className="text-muted-foreground/60 mt-0.5 text-[10px] break-words whitespace-normal">
                          {item.bsr_item_no}
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="text-right text-xs">{item.unit ?? "—"}</TableCell>
                    <TableCell className="text-right text-xs">
                      {item.quantity?.toFixed(2) ?? "—"}
                    </TableCell>
                    <TableCell className="text-right text-xs">
                      {item.rate?.toLocaleString() ?? "—"}
                    </TableCell>
                    <TableCell className="text-right text-xs font-medium">
                      {item.cost?.toLocaleString() ?? "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      <Badge
                        variant="outline"
                        className={`px-1.5 py-0.5 text-[10px] ${MATCH_BADGE[item.match_type ?? "no_match"] ?? MATCH_BADGE.no_match}`}
                      >
                        {item.match_type === "confirmed" && item.match_confidence != null
                          ? `${(item.match_confidence * 100).toFixed(0)}%`
                          : (item.match_type ?? "—")}
                      </Badge>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
            {page === totalPages && (
              <TableFooter>
                <TableRow>
                  <TableCell colSpan={6} className="text-xs font-semibold">
                    Grand Total (incl. contingencies)
                  </TableCell>
                  <TableCell className="text-right text-xs font-semibold">
                    LKR {grandTotal.toLocaleString()}
                  </TableCell>
                  <TableCell />
                </TableRow>
              </TableFooter>
            )}
          </Table>
        </div>
        {totalPages > 1 && (
          <div className="border-border text-muted-foreground flex items-center justify-between border-t px-4 py-3 text-xs">
            <span>
              {filtered.length} items, page {page} of {totalPages}
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                Prev
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export { CostBreakdownChart, ConfidenceBreakdownCard, FullBoqTable };
export type { BoqItem };

// ── Client-side Excel generator (extended with Audit sheet) ────────────────
export function generateExcelReport(data: Record<string, unknown>): ArrayBuffer {
  const wb = XLSX.utils.book_new();
  const projectInfo = (data.project_info as Record<string, unknown>) ?? {};
  const parameters = (projectInfo.parameters as Record<string, unknown>) ?? {};
  const costs = (data.costs as Record<string, unknown>) ?? {};
  const confidence = (data.confidence as Record<string, unknown>) ?? {};
  const boqItems = (data.boq_items as Record<string, unknown>[]) ?? [];

  // Summary
  const summaryRows: unknown[][] = [
    ["CONSTRUCTION COST ESTIMATION REPORT"],
    [],
    ["PROJECT DETAILS", ""],
    ["Building Type", projectInfo.building_type ?? "—"],
    ["Number of Floors", projectInfo.floors ?? "—"],
    ["Built-up Area", parameters.built_up_area ?? "—"],
    ["Finish Level", parameters.finish_level ?? "—"],
    ["Roof Type", parameters.roof_type ?? "—"],
    ["Ceiling Type", parameters.ceiling_type ?? "—"],
    ["Location", parameters.location ?? "—"],
    [],
    ["COST SUMMARY", ""],
    ["Base Total (LKR)", costs.base_total ?? 0],
    ["External Works Total (LKR)", costs.external_works_total ?? 0],
    ["Preliminaries", costs.preliminaries ?? 0],
    ["Contingencies", costs.contingencies ?? 0],
    ["Grand Total (LKR)", costs.total ?? 0],
    [],
    ["ESTIMATE QUALITY", ""],
    [
      "Confidence Score",
      String(((Number((confidence as Record<string, unknown>).score) || 0) * 100).toFixed(1)) + "%",
    ],
    ["Total BOQ Items", boqItems.length],
  ];
  const summarySheet = XLSX.utils.aoa_to_sheet(summaryRows);
  summarySheet["!cols"] = [{ wch: 30 }, { wch: 42 }];
  XLSX.utils.book_append_sheet(wb, summarySheet, "Summary");

  // BOQ
  const boqHeaders = [
    "No.",
    "Description",
    "Category",
    "Unit",
    "Quantity",
    "Rate (LKR)",
    "Cost (LKR)",
    "BSR Code",
    "Match %",
  ];
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
  boqRows.push([
    "",
    "",
    "",
    "",
    "",
    "GRAND TOTAL (incl. 5% Contingencies)",
    costs.total ?? 0,
    "",
    "",
  ]);
  const boqSheet = XLSX.utils.aoa_to_sheet(boqRows);
  boqSheet["!cols"] = [
    { wch: 6 },
    { wch: 48 },
    { wch: 26 },
    { wch: 10 },
    { wch: 12 },
    { wch: 16 },
    { wch: 16 },
    { wch: 18 },
    { wch: 10 },
  ];
  boqSheet["!freeze"] = { xSplit: 0, ySplit: 1 };
  XLSX.utils.book_append_sheet(wb, boqSheet, "Bill of Quantities");

  // Cost Breakdown
  const subtotals = (costs.subtotals as Record<string, number>) ?? {};
  const baseTotal = (costs.base_total as number) || 1;
  const breakdownRows: unknown[][] = [["Category", "Subtotal (LKR)", "% of Base Total"]];
  Object.entries(subtotals)
    .sort(([, a], [, b]) => b - a)
    .forEach(([cat, amount]) => {
      breakdownRows.push([
        cat.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
        amount,
        String(((amount / baseTotal) * 100).toFixed(1)) + "%",
      ]);
    });
  breakdownRows.push([]);
  breakdownRows.push(["Base Total", costs.base_total ?? 0, "100%"]);
  breakdownRows.push(["External Works Subtotal", costs.external_works_total ?? 0, ""]);
  breakdownRows.push(["Preliminaries", costs.preliminaries ?? 0, ""]);
  breakdownRows.push(["Contingencies", costs.contingencies ?? 0, ""]);
  breakdownRows.push(["Grand Total", costs.total ?? 0, ""]);
  const breakdownSheet = XLSX.utils.aoa_to_sheet(breakdownRows);
  breakdownSheet["!cols"] = [{ wch: 36 }, { wch: 20 }, { wch: 16 }];
  XLSX.utils.book_append_sheet(wb, breakdownSheet, "Cost Breakdown");

  // Audit sheet
  const auditHeaders = [
    "No.",
    "Description",
    "Match Type",
    "Match Confidence",
    "Qty Source",
    "Qty Confidence",
    "Needs Rate Review",
    "Warnings",
  ];
  const auditRows: unknown[][] = [auditHeaders];
  for (let i = 0; i < boqItems.length; i++) {
    const item = boqItems[i];
    auditRows.push([
      i + 1,
      item.description || item.bsr_description || "—",
      item.match_type || "—",
      item.match_confidence != null
        ? String(((item.match_confidence as number) * 100).toFixed(0)) + "%"
        : "—",
      item.quantity_source || "—",
      item.quantity_confidence_score != null
        ? String(((item.quantity_confidence_score as number) * 100).toFixed(0)) + "%"
        : "—",
      item.needs_rate_review ? "YES" : "no",
      (item.warnings as string[] | undefined)?.join("; ") ?? "",
    ]);
  }
  const auditSheet = XLSX.utils.aoa_to_sheet(auditRows);
  auditSheet["!cols"] = [
    { wch: 6 },
    { wch: 48 },
    { wch: 14 },
    { wch: 16 },
    { wch: 16 },
    { wch: 16 },
    { wch: 18 },
    { wch: 40 },
  ];
  auditSheet["!freeze"] = { xSplit: 0, ySplit: 1 };
  XLSX.utils.book_append_sheet(wb, auditSheet, "Audit");

  return XLSX.write(wb, { bookType: "xlsx", type: "array" }) as ArrayBuffer;
}

export function downloadExcelBlob(data: Record<string, unknown>): void {
  const buffer = generateExcelReport(data);
  const blob = new Blob([buffer], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
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
      <Button onClick={handleDownload}>
        <Download className="h-4 w-4" /> Download Excel Report
      </Button>
      <Button variant="outline" onClick={onNewEstimate}>
        New Estimate
      </Button>
    </div>
  );
}

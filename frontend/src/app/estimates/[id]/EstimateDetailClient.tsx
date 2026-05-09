"use client";

import { useState } from "react";
import {
  CostBreakdownChart,
  ConfidenceBreakdownCard,
  FullBoqTable,
  downloadExcelBlob,
  type BoqItem,
} from "@/components/results/ResultsComponents";
import { Download, FileText, TrendingUp, DollarSign, Edit3, Check, X } from "lucide-react";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

interface Estimate {
  id: string;
  project_name: string | null;
  notes: string | null;
  status: string;
  project_info: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
  confidence: number | null;
  grand_total: number | null;
  item_count: number | null;
  created_at: string;
}

export default function EstimateDetailClient({ estimate, accessToken }: { estimate: Estimate; userId?: string; accessToken: string }) {
  const [projectName, setProjectName] = useState(estimate.project_name ?? "");
  const [notes, setNotes] = useState(estimate.notes ?? "");
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  const result = estimate.result ?? {};
  const costs = (result.costs as Record<string, unknown>) ?? {};
  const confidence = (result.confidence as Record<string, unknown>) ?? {};
  const boqItems = (result.boq_items as BoqItem[]) ?? [];
  const subtotals = (costs.subtotals as Record<string, number>) ?? {};
  const grandTotal = Number(costs.total ?? estimate.grand_total ?? 0);

  const summaryCards = [
    { label: "Grand Total", value: `LKR ${grandTotal.toLocaleString()}`, icon: <DollarSign className="w-5 h-5 text-blue-400" /> },
    { label: "Confidence Score", value: `${((Number(confidence.score ?? estimate.confidence ?? 0)) * 100).toFixed(1)}%`, icon: <TrendingUp className="w-5 h-5 text-green-400" /> },
    { label: "BOQ Items", value: boqItems.length || estimate.item_count || 0, icon: <FileText className="w-5 h-5 text-purple-400" /> },
  ];

  const saveEdits = async () => {
    setSaving(true);
    try {
      await fetch(`${BACKEND_URL}/api/estimates/${estimate.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
        body: JSON.stringify({ project_name: projectName, notes }),
      });
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      {/* ── Metadata edit ── */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
        {editing ? (
          <div className="space-y-3">
            <div>
              <label className="text-xs text-zinc-400 mb-1 block">Project name</label>
              <input
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="text-xs text-zinc-400 mb-1 block">Notes</label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="flex gap-2">
              <button onClick={saveEdits} disabled={saving} className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-medium">
                <Check className="w-3 h-3" /> Save
              </button>
              <button onClick={() => setEditing(false)} className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-700 text-zinc-300 rounded-lg text-xs font-medium">
                <X className="w-3 h-3" /> Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm font-medium text-zinc-100">{projectName || "Untitled Project"}</p>
              {notes && <p className="text-xs text-zinc-400 mt-1">{notes}</p>}
            </div>
            <button onClick={() => setEditing(true)} className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg text-xs">
              <Edit3 className="w-3 h-3" /> Edit
            </button>
          </div>
        )}
      </div>

      {/* ── Summary cards ── */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {summaryCards.map((c) => (
          <div key={c.label} className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs text-zinc-400">{c.label}</p>
              {c.icon}
            </div>
            <p className="text-xl font-bold text-zinc-100">{c.value}</p>
          </div>
        ))}
      </div>

      {/* ── Confidence breakdown card (NEW-CONF-01) ── */}
      {Object.keys(confidence).length > 0 && (
        <ConfidenceBreakdownCard confidence={confidence} />
      )}

      {/* ── Cost breakdown chart (IMP-FE-07) ── */}
      {Object.keys(subtotals).length > 0 && (
        <CostBreakdownChart subtotals={subtotals} />
      )}

      {/* ── Full BOQ table (IMP-FE-01/02) ── */}
      {boqItems.length > 0 ? (
        <FullBoqTable items={boqItems} grandTotal={grandTotal} />
      ) : (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 text-center text-zinc-500 text-sm mb-6">
          No BOQ items available for this estimate.
        </div>
      )}

      {/* ── Actions ── */}
      <div className="flex gap-3">
        {result && boqItems.length > 0 && (
          <button
            onClick={() => downloadExcelBlob(result)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
          >
            <Download className="w-4 h-4" /> Download Excel Report
          </button>
        )}
      </div>
    </>
  );
}

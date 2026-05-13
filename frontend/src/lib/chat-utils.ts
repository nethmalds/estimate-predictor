import * as XLSX from "xlsx";

export function formatAssistantReply(result: unknown): string {
  if (typeof result === "string") return result;

  try {
    const r = result as Record<string, unknown>;

    if (r.status === "draft_boq") {
      const info = r.project_info as Record<string, unknown> | undefined;
      const items = (r.boq_items as Record<string, unknown>[]) ?? [];

      const paramLines = info?.parameters
        ? Object.entries(info.parameters as Record<string, unknown>)
            .map(([k, v]) => `  ${k}: ${v}`)
            .join("\n")
        : "";

      const itemLines = items
        .map((item, i) => {
          const desc = item.description ?? item.bsr_description ?? "—";
          const section = item.section ? `[${item.section}] ` : "";
          const unit = item.unit ? ` (${item.unit})` : "";
          const rate = item.rate != null ? ` @ ${item.rate}` : "";
          const conf =
            item.match_confidence != null
              ? ` — ${Math.round((item.match_confidence as number) * 100)}% match`
              : "";
          return `${i + 1}. ${section}${desc}${unit}${rate}${conf}`;
        })
        .join("\n");

      return [
        "Draft Bill of Quantities",
        "========================",
        paramLines ? `Project Parameters:\n${paramLines}\n` : "",
        `Items (${items.length}):`,
        itemLines || "  No items generated.",
      ]
        .filter(Boolean)
        .join("\n");
    }

    return JSON.stringify(result, null, 2);
  } catch {
    return "I received a response, but could not display it.";
  }
}

export function generateExcelReport(data: Record<string, unknown>): ArrayBuffer {
  const wb = XLSX.utils.book_new();
  const projectInfo = (data.project_info as Record<string, unknown>) || {};
  const parameters = (projectInfo.parameters as Record<string, unknown>) || {};
  const costs = (data.costs as Record<string, unknown>) || {};
  const confidence = (data.confidence as Record<string, unknown>) || {};
  const boqItems = (data.boq_items as Record<string, unknown>[]) || [];

  const summaryRows: unknown[][] = [
    ["CONSTRUCTION COST ESTIMATION REPORT"],
    [],
    ["PROJECT DETAILS", ""],
    ["Building Type", projectInfo.building_type || "—"],
    ["Number of Floors", projectInfo.floors || "—"],
    ["Bedrooms", parameters.bedrooms || "—"],
    ["Bathrooms", parameters.bathrooms || "—"],
    ["Built-up Area", parameters.built_up_area || "—"],
    ["Finish Level", parameters.finish_level || "—"],
    ["Roof Type", parameters.roof_type || "—"],
    ["Ceiling Type", parameters.ceiling_type || "—"],
    [],
    ["COST SUMMARY", ""],
    ["Base Total (LKR)", costs.base_total ?? 0],
    ["Contingencies (5%)", costs.contingencies ?? 0],
    ["Grand Total (LKR)", costs.total ?? 0],
    [],
    ["ESTIMATE QUALITY", ""],
    ["Confidence Score", `${(((confidence.score as number) || 0) * 100).toFixed(1)}%`],
    ["Total BOQ Items", boqItems.length],
  ];
  const summarySheet = XLSX.utils.aoa_to_sheet(summaryRows);
  summarySheet["!cols"] = [{ wch: 30 }, { wch: 42 }];
  XLSX.utils.book_append_sheet(wb, summarySheet, "Summary");

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
      conf != null ? `${(conf * 100).toFixed(0)}%` : "—",
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
  XLSX.utils.book_append_sheet(wb, boqSheet, "Bill of Quantities");

  const subtotals = (costs.subtotals as Record<string, number>) || {};
  const baseTotal = (costs.base_total as number) || 1;
  const breakdownRows: unknown[][] = [["Category", "Subtotal (LKR)", "% of Base Total"]];
  Object.entries(subtotals)
    .sort(([, a], [, b]) => b - a)
    .forEach(([cat, amount]) => {
      breakdownRows.push([
        cat.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
        amount,
        `${((amount / baseTotal) * 100).toFixed(1)}%`,
      ]);
    });
  breakdownRows.push([]);
  breakdownRows.push(["Base Total", costs.base_total ?? 0, "100%"]);
  breakdownRows.push(["Contingencies (5%)", costs.contingencies ?? 0, ""]);
  breakdownRows.push(["Grand Total", costs.total ?? 0, ""]);
  const breakdownSheet = XLSX.utils.aoa_to_sheet(breakdownRows);
  breakdownSheet["!cols"] = [{ wch: 36 }, { wch: 20 }, { wch: 16 }];
  XLSX.utils.book_append_sheet(wb, breakdownSheet, "Cost Breakdown");

  return XLSX.write(wb, { bookType: "xlsx", type: "array" }) as ArrayBuffer;
}

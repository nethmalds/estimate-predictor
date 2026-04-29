"use client";

import { useState, FormEvent, useRef, useEffect, useCallback } from "react";
import * as XLSX from "xlsx";
import { uploadFiles, useUploadThing } from "@/lib/uploadthing";
import {
  openClarificationStream,
  startClarificationSession,
  submitClarificationAnswer,
} from "../services/estimation";
import { Message, ExcelPreviewRow, UploadState } from "@/types/chat";
import { ChatInput } from "@/components/chat/ChatInput";
import { ChatMessage } from "@/components/chat/ChatMessage";

// ─── BOQ formatter ───────────────────────────────────────────────────────────

function formatAssistantReply(result: unknown): string {
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

// ─── Excel generator (client-side, SheetJS) ───────────────────────────────────

function generateExcelReport(data: Record<string, unknown>): ArrayBuffer {
  const wb = XLSX.utils.book_new();
  const projectInfo = (data.project_info as Record<string, unknown>) || {};
  const parameters  = (projectInfo.parameters as Record<string, unknown>) || {};
  const costs       = (data.costs as Record<string, unknown>) || {};
  const confidence  = (data.confidence as Record<string, unknown>) || {};
  const boqItems    = (data.boq_items as Record<string, unknown>[]) || [];

  // ── Sheet 1: Summary ────────────────────────────────────────────────────────
  const summaryRows: unknown[][] = [
    ["CONSTRUCTION COST ESTIMATION REPORT"],
    [],
    ["PROJECT DETAILS", ""],
    ["Building Type",    projectInfo.building_type  || "—"],
    ["Number of Floors", projectInfo.floors         || "—"],
    ["Bedrooms",         parameters.bedrooms        || "—"],
    ["Bathrooms",        parameters.bathrooms       || "—"],
    ["Built-up Area",    parameters.built_up_area   || "—"],
    ["Finish Level",     parameters.finish_level    || "—"],
    ["Roof Type",        parameters.roof_type       || "—"],
    ["Ceiling Type",     parameters.ceiling_type    || "—"],
    [],
    ["COST SUMMARY", ""],
    ["Base Total (LKR)",   costs.base_total   ?? 0],
    ["Contingencies (5%)", costs.contingencies ?? 0],
    ["Grand Total (LKR)",  costs.total        ?? 0],
    [],
    ["ESTIMATE QUALITY", ""],
    ["Confidence Score", `${((confidence.score as number || 0) * 100).toFixed(1)}%`],
    ["Total BOQ Items",  boqItems.length],
  ];
  const summarySheet = XLSX.utils.aoa_to_sheet(summaryRows);
  summarySheet["!cols"] = [{ wch: 30 }, { wch: 42 }];
  XLSX.utils.book_append_sheet(wb, summarySheet, "Summary");

  // ── Sheet 2: Bill of Quantities ─────────────────────────────────────────────
  const boqHeaders = ["No.", "Description", "Category", "Unit", "Quantity", "Rate (LKR)", "Cost (LKR)", "BSR Code", "Match %"];
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
  boqRows.push(["", "", "", "", "", "GRAND TOTAL (incl. 5% Contingencies)", costs.total ?? 0, "", ""]);
  const boqSheet = XLSX.utils.aoa_to_sheet(boqRows);
  boqSheet["!cols"] = [
    { wch: 6 }, { wch: 48 }, { wch: 26 }, { wch: 10 },
    { wch: 12 }, { wch: 16 }, { wch: 16 }, { wch: 18 }, { wch: 10 },
  ];
  XLSX.utils.book_append_sheet(wb, boqSheet, "Bill of Quantities");

  // ── Sheet 3: Cost Breakdown ─────────────────────────────────────────────────
  const subtotals = (costs.subtotals as Record<string, number>) || {};
  const baseTotal  = (costs.base_total as number) || 1;
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
  breakdownRows.push(["Base Total",         costs.base_total   ?? 0, "100%"]);
  breakdownRows.push(["Contingencies (5%)", costs.contingencies ?? 0, ""]);
  breakdownRows.push(["Grand Total",        costs.total        ?? 0, ""]);
  const breakdownSheet = XLSX.utils.aoa_to_sheet(breakdownRows);
  breakdownSheet["!cols"] = [{ wch: 36 }, { wch: 20 }, { wch: 16 }];
  XLSX.utils.book_append_sheet(wb, breakdownSheet, "Cost Breakdown");

  return XLSX.write(wb, { bookType: "xlsx", type: "array" }) as ArrayBuffer;
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Hello! I'm your project estimation assistant.\n\nDescribe your construction project and I'll generate a detailed Bill of Quantities. You can also attach a floor plan image using the + button.",
    },
  ]);
  const [input, setInput] = useState("");
  const [uploadState, setUploadState] = useState<UploadState>({ status: "idle" });
  const [isLoading, setIsLoading] = useState(false);
  const [clarificationSessionId, setClarificationSessionId] = useState<string | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ─── UploadThing hook ──────────────────────────────────────────────────────
  const { startUpload, isUploading } = useUploadThing("floorplanUploader", {
    onClientUploadComplete: (res) => {
      const file = res?.[0];
      if (file) {
        setUploadState((prev) =>
          prev.status === "uploading"
            ? { status: "done", fileName: prev.fileName, previewUrl: prev.previewUrl, url: file.ufsUrl, fileKey: file.key }
            : prev
        );
      }
    },
    onUploadError: (err) => {
      setUploadState({ status: "error", message: err.message || "Upload failed. Please try again." });
      setTimeout(() => setUploadState({ status: "idle" }), 3000);
    },
  });

  // ─── Auto-scroll ───────────────────────────────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // ─── Cleanup EventSource on unmount ───────────────────────────────────────
  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
    };
  }, []);

  // ─── Auto-resize textarea ─────────────────────────────────────────────────
  const resizeTextarea = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, []);

  useEffect(() => {
    resizeTextarea();
  }, [input, resizeTextarea]);

  // ─── File select ───────────────────────────────────────────────────────────
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const previewUrl = file.type.startsWith("image/") ? URL.createObjectURL(file) : null;
    setUploadState({ status: "uploading", fileName: file.name, previewUrl });

    await startUpload([file]);

    // Reset file input so the same file can be re-selected if cleared
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const clearUpload = (deleteFromStorage = false) => {
    if (uploadState.status === "uploading" || uploadState.status === "done") {
      const prev = uploadState as { previewUrl?: string | null; fileKey?: string };
      if (prev.previewUrl) URL.revokeObjectURL(prev.previewUrl);

      if (deleteFromStorage && uploadState.status === "done" && prev.fileKey) {
        fetch("/api/uploadthing/delete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ fileKey: prev.fileKey }),
        }).catch((err) => console.error("Failed to delete file from UploadThing:", err));
      }
    }
    setUploadState({ status: "idle" });
  };

  // ─── Submit ────────────────────────────────────────────────────────────────
  const handleSubmit = async (e?: FormEvent) => {
    e?.preventDefault();
    const trimmedInput = input.trim();
    if (!trimmedInput || isLoading || isUploading) return;

    const isClarifying = Boolean(clarificationSessionId);

    const userMsg: Message = { role: "user", content: trimmedInput };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setIsLoading(true);

    if (isClarifying && clarificationSessionId) {
      try {
        await submitClarificationAnswer(clarificationSessionId, trimmedInput);
        // Reset loading so the UI doesn't freeze between question events.
        // The next SSE event (question / info / completed) will manage state from here.
        setIsLoading(false);
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown error.";
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: `Sorry, I couldn't submit the clarification. ${message}` },
        ]);
        // Close the broken session so the next message starts fresh.
        setClarificationSessionId(null);
        setCurrentQuestion(null);
        eventSourceRef.current?.close();
        setIsLoading(false);
      }
      return;
    }

    const floorplanUrl =
      uploadState.status === "done" ? uploadState.url : null;
    clearUpload(false);

    try {
      const result = await startClarificationSession({
        description: trimmedInput,
        floorplanImageUrl: floorplanUrl,
      });

      setClarificationSessionId(result.session_id);
      setCurrentQuestion(null);
      eventSourceRef.current?.close();
      const source = openClarificationStream(result.session_id);
      eventSourceRef.current = source;

      source.addEventListener("question", (event) => {
        const data = JSON.parse((event as MessageEvent).data) as { question: string };
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: data.question },
        ]);
        setCurrentQuestion(data.question);
        setIsLoading(false);
      });

      let streamCompleted = false;

      source.addEventListener("completed", (event) => {
        streamCompleted = true;
        const data = JSON.parse((event as MessageEvent).data) as Record<string, unknown>;

        setClarificationSessionId(null);
        setCurrentQuestion(null);
        setIsLoading(false);
        source.close();

        // Build preview rows (first 5 BOQ items)
        const boqItems = (data.boq_items as Record<string, unknown>[]) || [];
        const preview: ExcelPreviewRow[] = boqItems.slice(0, 5).map((item) => ({
          description: String(item.description || item.bsr_description || "—"),
          unit:        String(item.unit || "—"),
          quantity:    Number(item.quantity ?? 0),
          rate:        Number(item.rate ?? 0),
          cost:        Number(item.cost ?? 0),
        }));
        const costs = (data.costs as Record<string, unknown>) || {};
        const excelTotal = Number(costs.total ?? 0);

        // Generate Excel and upload to UploadThing asynchronously
        void (async () => {
          try {
            const excelBuffer = generateExcelReport(data);
            const blob = new Blob([excelBuffer], {
              type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            });
            const fileName = `estimate_${new Date().toISOString().slice(0, 10)}.xlsx`;
            const file = new File([blob], fileName, { type: blob.type });
            const [uploaded] = await uploadFiles("excelUploader", { files: [file] });
            setMessages((prev) => [
              ...prev,
              {
                role: "excel",
                content: "Your cost estimate is ready as an Excel report.",
                excelUrl: uploaded.ufsUrl,
                fileName,
                excelPreview: preview,
                excelTotal,
              },
            ]);
          } catch (err) {
            console.error("Excel generation or upload failed:", err);
          }
        })();
      });

      source.addEventListener("info", (event) => {
        const data = JSON.parse((event as MessageEvent).data) as { message: string };
        setMessages((prev) => [...prev, { role: "info", content: data.message }]);
        setCurrentQuestion(null);
        // Show loading indicator while the estimation pipeline runs (~1-2 min)
        setIsLoading(true);
      });

      source.addEventListener("progress", (event) => {
        const data = JSON.parse((event as MessageEvent).data) as {
          step: string;
          status: string;
          [key: string]: unknown;
        };
        // Log all pipeline progress events to the browser console for debugging.
        // Note: 'dev_log' events are filtered on the backend and never arrive here.
        console.log(`[PIPELINE] step=${data.step} status=${data.status}`, data);
      });

      source.addEventListener("error", (event) => {
        streamCompleted = true;
        const raw = (event as MessageEvent).data;
        const msg = raw
          ? (JSON.parse(raw) as { message?: string }).message ?? "An error occurred."
          : "An error occurred during estimation.";
        setMessages((prev) => [...prev, { role: "assistant", content: msg }]);
        setClarificationSessionId(null);
        setCurrentQuestion(null);
        setIsLoading(false);
        source.close();
      });

      source.onerror = () => {
        if (streamCompleted) return;
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: "Sorry, the connection was lost. Please try again." },
        ]);
        setClarificationSessionId(null);
        setCurrentQuestion(null);
        setIsLoading(false);
        source.close();
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error.";
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Sorry, I couldn't estimate the project. ${message}` },
      ]);
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleNewChat = () => {
    eventSourceRef.current?.close();
    setMessages([
      {
        role: "assistant",
        content:
          "Hello! I'm your project estimation assistant.\n\nDescribe your construction project and I'll generate a detailed Bill of Quantities. You can also attach a floor plan image using the + button.",
      },
    ]);
    setInput("");
    setClarificationSessionId(null);
    setCurrentQuestion(null);
    setIsLoading(false);
    clearUpload(true);
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  useEffect(() => {
    const handleSidebarNewChat = () => {
      handleNewChat();
    };

    window.addEventListener("chat:new", handleSidebarNewChat);
    return () => window.removeEventListener("chat:new", handleSidebarNewChat);
  }, [handleNewChat]);

  return (
    <div className="flex flex-1 flex-col bg-[#212121]">
      {/* Message list */}
      <main className="flex-1 max-w-5xl mx-auto overflow-y-auto py-6 pb-2" aria-label="Conversation">
        <div className="px-6 flex flex-col">
          {messages.map((msg, idx) => (
            <ChatMessage key={idx} msg={msg} />
          ))}

          {/* Typing indicator */}
          {isLoading && (
            <div
              className="flex items-center gap-3 py-1 pb-3"
              aria-label="Assistant is typing"
              role="status"
            >
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center text-[13px] font-bold text-white shrink-0 shadow-sm"
                style={{ background: "linear-gradient(135deg, #18181b, #09090b)" }}
                aria-hidden="true"
              >
                E
              </div>
              <div className="flex gap-1 items-center" aria-hidden="true">
                <span className="w-1.5 h-1.5 rounded-full bg-zinc-500 animate-dot-pulse" />
                <span className="w-1.5 h-1.5 rounded-full bg-zinc-500 animate-dot-pulse [animation-delay:0.2s]" />
                <span className="w-1.5 h-1.5 rounded-full bg-zinc-500 animate-dot-pulse [animation-delay:0.4s]" />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} aria-hidden="true" />
        </div>
      </main>

      {/* Input composer */}
      <div className="px-6 pb-5 pt-3">
        <div className="w-full">
          <ChatInput
            input={input}
            setInput={setInput}
            isLoading={isLoading}
            isUploading={isUploading}
            uploadState={uploadState}
            clarificationSessionId={clarificationSessionId}
            currentQuestion={currentQuestion}
            textareaRef={textareaRef}
            fileInputRef={fileInputRef}
            handleSubmit={handleSubmit}
            handleKeyDown={handleKeyDown}
            handleFileChange={handleFileChange}
            clearUpload={clearUpload}
            resizeTextarea={resizeTextarea}
          />
          <p className="text-xs text-zinc-500 text-center mt-2">
            Press <kbd className="font-mono">Enter</kbd> to send ·{" "}
            <kbd className="font-mono">Shift+Enter</kbd> for a new line
          </p>
        </div>
      </div>
    </div>
  );
}

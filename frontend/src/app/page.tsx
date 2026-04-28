"use client";

import { useState, FormEvent, useRef, useEffect, useCallback } from "react";
import { useUploadThing } from "@/lib/uploadthing";
import {
  openClarificationStream,
  startClarificationSession,
  submitClarificationAnswer,
} from "../services/estimation";

// ─── Types ───────────────────────────────────────────────────────────────────

type MessageRole = "user" | "assistant" | "info";

type Message = {
  role: MessageRole;
  content: string;
};

type UploadState =
  | { status: "idle" }
  | { status: "uploading"; fileName: string; previewUrl: string | null }
  | { status: "done"; fileName: string; previewUrl: string | null; url: string; fileKey: string }
  | { status: "error"; message: string };

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

// ─── Icons (inline SVG) ───────────────────────────────────────────────────────

function PlusIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M8 13V3M3 8l5-5 5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function NewChatIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path d="M7 2v10M2 7h10" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
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
        const data = JSON.parse((event as MessageEvent).data) as unknown;
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: formatAssistantReply(data) },
        ]);
        setClarificationSessionId(null);
        setCurrentQuestion(null);
        setIsLoading(false);
        source.close();
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

  const canSend = input.trim().length > 0 && !isLoading && !isUploading;

  // ─── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="app-shell">
      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <aside className="sidebar" aria-label="Sidebar">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon" aria-hidden="true">E</div>
          <div>
            <div className="sidebar-logo-text">EstimateAI</div>
            <div className="sidebar-logo-sub">Construction Estimator</div>
          </div>
        </div>

        <button
          id="new-chat-btn"
          className="new-chat-btn"
          onClick={handleNewChat}
          aria-label="Start a new chat"
        >
          <NewChatIcon />
          New Chat
        </button>

        <div className="sidebar-section-title">Recent</div>
        <div className="sidebar-chat-item" aria-hidden="true">Project estimation session</div>
        <div className="sidebar-chat-item" aria-hidden="true">BOQ generation</div>
        <div className="sidebar-chat-item" aria-hidden="true">Floor plan analysis</div>
      </aside>

      {/* ── Chat area ────────────────────────────────────────────────────── */}
      <div className="chat-area">
        {/* Message list */}
        <main className="messages-list" id="messages-list" aria-label="Conversation">
          <div className="messages-inner">
            {messages.map((msg, idx) => {
              if (msg.role === "info") {
                return (
                  <div key={idx} className="message-row message-row--info" role="status">
                    <div className="message-bubble--info">{msg.content}</div>
                  </div>
                );
              }

              if (msg.role === "user") {
                return (
                  <div key={idx} className="message-row message-row--user">
                    <div className="message-bubble--user" aria-label="Your message">
                      {msg.content}
                    </div>
                  </div>
                );
              }

              // assistant
              return (
                <div key={idx} className="message-row message-row--assistant">
                  <div className="assistant-avatar" aria-hidden="true">E</div>
                  <div className="message-bubble--assistant" aria-label="Assistant response">
                    {msg.content}
                  </div>
                </div>
              );
            })}

            {/* Typing indicator */}
            {isLoading && (
              <div className="typing-indicator" aria-label="Assistant is typing" role="status">
                <div className="assistant-avatar" aria-hidden="true">E</div>
                <div className="typing-dots" aria-hidden="true">
                  <div className="typing-dot" />
                  <div className="typing-dot" />
                  <div className="typing-dot" />
                </div>
              </div>
            )}

            <div ref={messagesEndRef} aria-hidden="true" />
          </div>
        </main>

        {/* Input composer */}
        <div className="composer-wrapper">
          <div className="composer-inner">
            <form onSubmit={handleSubmit} aria-label="Send a message">
              <div className="composer-box">
                {/* Upload chip (shown when file attached) */}
                {uploadState.status !== "idle" && uploadState.status !== "error" && (
                  <div className="chip-row">
                    <div className="upload-chip" role="status" aria-label="Attached file">
                      {uploadState.previewUrl ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={uploadState.previewUrl}
                          alt="Floor plan preview"
                          className="chip-thumb"
                        />
                      ) : (
                        <div className="chip-thumb-placeholder" aria-hidden="true">📄</div>
                      )}
                      <span className="chip-name">{uploadState.fileName}</span>
                      {uploadState.status === "uploading" && (
                        <div className="chip-spinner" aria-label="Uploading..." />
                      )}
                      {uploadState.status === "done" && (
                        <span className="chip-status">✓</span>
                      )}
                      <button
                        type="button"
                        className="chip-clear"
                        onClick={() => clearUpload(true)}
                        aria-label="Remove attachment"
                        disabled={uploadState.status === "uploading"}
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                )}

                {uploadState.status === "error" && (
                  <div className="chip-row">
                    <span style={{ fontSize: 12, color: "#e06c75" }}>
                      ⚠ {uploadState.message}
                    </span>
                  </div>
                )}

                {/* Textarea row */}
                <div className="composer-row">
                  {/* Hidden file input */}
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*,.pdf"
                    onChange={handleFileChange}
                    style={{ display: "none" }}
                    id="floor-plan-file-input"
                    aria-label="Upload floor plan"
                    disabled={isLoading || Boolean(clarificationSessionId)}
                  />

                  {/* + Upload button */}
                  <button
                    type="button"
                    id="upload-floor-plan-btn"
                    className="upload-btn"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={
                      isLoading ||
                      Boolean(clarificationSessionId) ||
                      uploadState.status === "uploading"
                    }
                    aria-label="Attach floor plan image"
                    title="Attach floor plan"
                  >
                    <PlusIcon />
                  </button>

                  {/* Textarea */}
                  <textarea
                    ref={textareaRef}
                    id="message-input"
                    className="composer-textarea"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    onInput={resizeTextarea}
                    placeholder={
                      currentQuestion
                        ? "Type your answer…"
                        : "Describe your project…"
                    }
                    disabled={isLoading}
                    rows={1}
                    aria-label="Message input"
                    aria-multiline="true"
                  />

                  {/* Send button */}
                  <button
                    type="submit"
                    id="send-message-btn"
                    className="send-btn"
                    disabled={!canSend}
                    aria-label="Send message"
                    title="Send (Enter)"
                  >
                    <SendIcon />
                  </button>
                </div>
              </div>
            </form>

            <p className="composer-hint">
              Press <kbd style={{ fontFamily: "monospace" }}>Enter</kbd> to send ·{" "}
              <kbd style={{ fontFamily: "monospace" }}>Shift+Enter</kbd> for a new line
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

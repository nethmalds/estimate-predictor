"use client";

import { useState, FormEvent, useRef, useEffect } from "react";
import {
  openClarificationStream,
  startClarificationSession,
  submitClarificationAnswer,
} from "../services/estimation";

type Message = {
  role: "user" | "assistant";
  content: string;
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "Hello! How can I help you estimate your project today?" }
  ]);
  const [input, setInput] = useState("");
  const [floorplanUrl, setFloorplanUrl] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [clarificationSessionId, setClarificationSessionId] = useState<string | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
    };
  }, []);

  const formatAssistantReply = (result: unknown) => {
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
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const trimmedInput = input.trim();
    if (!trimmedInput || isLoading) return;

    const isClarifying = Boolean(clarificationSessionId);

    const userMsg: Message = { role: "user", content: trimmedInput };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);

    if (isClarifying && clarificationSessionId) {
      try {
        await submitClarificationAnswer(clarificationSessionId, trimmedInput);
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown error.";
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: `Sorry, I couldn't submit the clarification. ${message}` }
        ]);
        setIsLoading(false);
      }
      return;
    }

    const trimmedFloorplanUrl = floorplanUrl.trim();
    setFloorplanUrl("");

    try {
      const result = await startClarificationSession({
        description: trimmedInput,
        floorplanImageUrl: trimmedFloorplanUrl || null,
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
          { role: "assistant", content: data.question }
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
          { role: "assistant", content: formatAssistantReply(data) }
        ]);
        setClarificationSessionId(null);
        setCurrentQuestion(null);
        setIsLoading(false);
        source.close();
      });

      source.addEventListener("info", (event) => {
        const data = JSON.parse((event as MessageEvent).data) as { message: string };
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: data.message }
        ]);
        setCurrentQuestion(null);
      });

      source.addEventListener("progress", (event) => {
        const data = JSON.parse((event as MessageEvent).data) as { step: string, status: string, output?: unknown };
        if (data.status === "dev_log") {
          console.log(`[DEV LOG] Output from backend step: ${data.step}`);
          console.log(data.output);
        }
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
          { role: "assistant", content: "Sorry, the connection was lost. Please try again." }
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
        { role: "assistant", content: `Sorry, I couldn't estimate the project. ${message}` }
      ]);
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-zinc-50 dark:bg-zinc-900 font-sans">
      {/* Header */}
      <header className="flex items-center justify-center py-4 bg-white dark:bg-black border-b border-zinc-200 dark:border-zinc-800 shadow-sm shrink-0">
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">Project Estimation Assistant</h1>
      </header>

      {/* Chat Messages */}
      <main className="flex-1 overflow-y-auto w-full">
        <div className="max-w-3xl mx-auto p-4 space-y-6">
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex w-full ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] px-5 py-3.5 rounded-2xl shadow-sm ${msg.role === "user"
                  ? "bg-blue-600 text-white rounded-br-sm"
                  : "bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 border border-zinc-200 dark:border-zinc-700 rounded-bl-sm"
                  }`}
              >
                <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} className="h-4" />
        </div>
      </main>

      {/* Input Area */}
      <div className="bg-white dark:bg-black border-t border-zinc-200 dark:border-zinc-800 p-4 w-full shrink-0">
        <form onSubmit={handleSubmit} className="w-full max-w-3xl mx-auto flex flex-col gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              currentQuestion
                ? "Type your answer here..."
                : "Type your project description here..."
            }
            disabled={isLoading}
            className="px-5 py-3.5 rounded-full border border-zinc-300 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm"
          />
          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              type="url"
              value={floorplanUrl}
              onChange={(e) => setFloorplanUrl(e.target.value)}
              placeholder="Optional floor plan URL"
              disabled={isLoading || Boolean(clarificationSessionId)}
              className="flex-1 px-5 py-3.5 rounded-full border border-zinc-300 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm"
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="px-8 py-3.5 rounded-full bg-blue-600 text-white font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:hover:bg-blue-600 shadow-sm"
            >
              {isLoading ? "Sending..." : "Send"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

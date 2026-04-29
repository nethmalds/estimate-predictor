import { useState } from "react";
import { Message, QuestionMetadata } from "@/types/chat";
import { ExcelIcon } from "@/components/icons";
import { Download, AlertTriangle } from "lucide-react";

interface ChatMessageProps {
  msg: Message;
  /** Called when the user selects an option from an inline widget */
  onWidgetSubmit?: (answer: string) => void;
}

// ---------------------------------------------------------------------------
// Inline input widgets
// ---------------------------------------------------------------------------

/** Chip-style button group for dropdown questions */
function DropdownWidget({
  options,
  onSelect,
}: {
  options: { value: string; label: string }[];
  onSelect: (value: string) => void;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  return (
    <div className="flex flex-wrap gap-2 mt-3" role="group" aria-label="Select an option">
      {options.map((opt) => (
        <button
          key={opt.value}
          id={`option-${opt.value}`}
          onClick={() => {
            setSelected(opt.value);
            onSelect(opt.value);
          }}
          disabled={selected !== null}
          className={`px-4 py-2 rounded-xl text-[13px] font-medium border transition-all duration-150 cursor-pointer
            ${
              selected === opt.value
                ? "bg-zinc-100 text-zinc-900 border-zinc-100"
                : "bg-zinc-900 text-zinc-200 border-zinc-700 hover:bg-zinc-800 hover:border-zinc-500"
            }
            ${selected !== null && selected !== opt.value ? "opacity-40 cursor-default" : ""}
          `}
          aria-pressed={selected === opt.value}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

/** Preset range selector + optional custom numeric input for built_up_area */
function AreaPickerWidget({
  presets,
  customUnits,
  onSelect,
}: {
  presets: { value: string; label: string }[];
  customUnits: string[];
  onSelect: (value: string) => void;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [showCustom, setShowCustom] = useState(false);
  const [customVal, setCustomVal] = useState("");
  const [unit, setUnit] = useState(customUnits[0] ?? "sqft");
  const [submitted, setSubmitted] = useState(false);

  function handlePreset(val: string) {
    if (submitted) return;
    setSelected(val);
    setShowCustom(false);
    setSubmitted(true);
    onSelect(val);
  }

  function handleCustomSubmit() {
    if (submitted || !customVal.trim()) return;
    const answer = `${customVal.trim()} ${unit}`;
    setSubmitted(true);
    setSelected("custom");
    onSelect(answer);
  }

  return (
    <div className="mt-3 space-y-2">
      <div className="flex flex-wrap gap-2" role="group" aria-label="Select built-up area">
        {presets.map((p) => (
          <button
            key={p.value}
            id={`area-preset-${p.value}`}
            onClick={() => handlePreset(p.value)}
            disabled={submitted}
            className={`px-3 py-1.5 rounded-xl text-[13px] font-medium border transition-all duration-150 cursor-pointer
              ${
                selected === p.value
                  ? "bg-zinc-100 text-zinc-900 border-zinc-100"
                  : "bg-zinc-900 text-zinc-200 border-zinc-700 hover:bg-zinc-800 hover:border-zinc-500"
              }
              ${submitted && selected !== p.value ? "opacity-40 cursor-default" : ""}
            `}
            aria-pressed={selected === p.value}
          >
            {p.label}
          </button>
        ))}
        {!submitted && (
          <button
            id="area-custom-toggle"
            onClick={() => setShowCustom((v) => !v)}
            className="px-3 py-1.5 rounded-xl text-[13px] font-medium border border-dashed border-zinc-600 text-zinc-400 hover:border-zinc-400 hover:text-zinc-200 transition-all duration-150 cursor-pointer"
          >
            Enter custom size
          </button>
        )}
      </div>
      {showCustom && !submitted && (
        <div className="flex items-center gap-2 mt-2">
          <input
            id="area-custom-input"
            type="number"
            min={1}
            placeholder="e.g. 2000"
            value={customVal}
            onChange={(e) => setCustomVal(e.target.value)}
            className="w-32 px-3 py-1.5 rounded-xl bg-zinc-900 border border-zinc-700 text-zinc-100 text-[13px] focus:outline-none focus:border-zinc-400"
            aria-label="Custom built-up area value"
            onKeyDown={(e) => e.key === "Enter" && handleCustomSubmit()}
          />
          <div className="flex rounded-xl overflow-hidden border border-zinc-700">
            {customUnits.map((u) => (
              <button
                key={u}
                onClick={() => setUnit(u)}
                className={`px-3 py-1.5 text-[12px] font-medium transition-colors cursor-pointer
                  ${unit === u ? "bg-zinc-700 text-zinc-100" : "bg-zinc-900 text-zinc-400 hover:bg-zinc-800"}`}
                aria-pressed={unit === u}
              >
                {u}
              </button>
            ))}
          </div>
          <button
            id="area-custom-submit"
            onClick={handleCustomSubmit}
            className="px-4 py-1.5 rounded-xl bg-zinc-700 hover:bg-zinc-600 text-zinc-100 text-[13px] font-medium transition-colors cursor-pointer"
          >
            Confirm
          </button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main ChatMessage component
// ---------------------------------------------------------------------------

export function ChatMessage({ msg, onWidgetSubmit }: ChatMessageProps) {
  // ── Validation error banner (e.g. floors=0) ─────────────────────────────
  if (msg.role === "validation_error") {
    return (
      <div
        className="flex items-start gap-3 w-full my-2 px-4 py-3 rounded-xl bg-amber-950/40 border border-amber-700/40"
        role="alert"
        aria-live="assertive"
      >
        <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" aria-hidden="true" />
        <span className="text-[14px] text-amber-300 leading-relaxed">{msg.content}</span>
      </div>
    );
  }

  // ── Info pill ────────────────────────────────────────────────────────────
  if (msg.role === "info") {
    return (
      <div className="flex w-full justify-center my-3" role="status">
        <div className="text-[12px] text-zinc-500 italic text-center px-4 py-1.5 bg-zinc-900 rounded-full">
          {msg.content}
        </div>
      </div>
    );
  }

  // ── User message ─────────────────────────────────────────────────────────
  if (msg.role === "user") {
    return (
      <div className="flex w-full justify-end my-4">
        <div
          className="bg-zinc-800 border border-zinc-700 text-zinc-100 px-5 py-3.5 rounded-3xl rounded-br-md shadow-sm max-w-[75%] text-[15px] leading-relaxed wrap-break-word whitespace-pre-wrap font-inter"
          aria-label="Your message"
        >
          {msg.content}
        </div>
      </div>
    );
  }

  // ── Excel result card ────────────────────────────────────────────────────
  if (msg.role === "excel") {
    return (
      <div className="flex w-full justify-start my-4 mt-2">
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center text-[13px] font-bold text-white shrink-0 mr-4 mt-0.5 shadow-sm"
          style={{ background: "linear-gradient(135deg, #18181b, #09090b)" }}
          aria-hidden="true"
        >
          E
        </div>
        <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-5 shadow-sm max-w-162.5 w-full">
          <div className="flex items-center gap-3 mb-2">
            <ExcelIcon />
            <span className="text-[15px] font-semibold text-emerald-500">Cost Estimate — Excel Report</span>
          </div>
          <p className="text-[14px] text-zinc-400 mb-5 leading-relaxed">{msg.content}</p>

          {msg.excelPreview && msg.excelPreview.length > 0 && (
            <div className="mb-5 rounded-xl overflow-hidden border border-zinc-800 bg-zinc-950">
              <table className="w-full border-collapse text-[13px]" aria-label="BOQ preview">
                <thead>
                  <tr className="bg-zinc-900">
                    <th className="px-4 py-2.5 text-left text-zinc-400 font-medium whitespace-nowrap border-b border-zinc-800">Description</th>
                    <th className="px-4 py-2.5 text-left text-zinc-400 font-medium whitespace-nowrap border-b border-zinc-800">Unit</th>
                    <th className="px-4 py-2.5 text-left text-zinc-400 font-medium whitespace-nowrap border-b border-zinc-800">Qty</th>
                    <th className="px-4 py-2.5 text-left text-zinc-400 font-medium whitespace-nowrap border-b border-zinc-800">Rate</th>
                    <th className="px-4 py-2.5 text-left text-zinc-400 font-medium whitespace-nowrap border-b border-zinc-800">Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {msg.excelPreview.map((row, ri) => (
                    <tr key={ri} className="hover:bg-zinc-900/50 transition-colors">
                      <td className="px-4 py-2.5 text-zinc-300 border-b border-zinc-800/50 align-top max-w-60 whitespace-nowrap overflow-hidden text-ellipsis">{row.description}</td>
                      <td className="px-4 py-2.5 text-zinc-300 border-b border-zinc-800/50 align-top">{row.unit}</td>
                      <td className="px-4 py-2.5 text-zinc-300 border-b border-zinc-800/50 align-top text-right tabular-nums whitespace-nowrap">{row.quantity.toLocaleString()}</td>
                      <td className="px-4 py-2.5 text-zinc-300 border-b border-zinc-800/50 align-top text-right tabular-nums whitespace-nowrap">{row.rate.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                      <td className="px-4 py-2.5 text-zinc-300 border-b border-zinc-800/50 align-top text-right tabular-nums whitespace-nowrap">{row.cost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {(msg.excelTotal ?? 0) > 0 && (
                <div className="flex justify-between items-center px-4 py-3 bg-zinc-900/80 border-t border-zinc-800">
                  <span className="text-[13px] font-medium text-emerald-500">Grand Total</span>
                  <span className="text-[14px] font-bold text-emerald-400 tabular-nums">
                    LKR {(msg.excelTotal!).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                </div>
              )}
            </div>
          )}

          <div className="flex gap-3">
            <a
              href={msg.excelUrl}
              download={msg.fileName}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-600/10 border border-emerald-600/20 text-emerald-500 text-[14px] font-medium no-underline transition-colors hover:bg-emerald-600/20 hover:text-emerald-400"
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`Download ${msg.fileName}`}
            >
              <Download className="w-4 h-4" />
              Download Excel
            </a>
          </div>
        </div>
      </div>
    );
  }

  // ── Assistant message (may include an inline input widget) ───────────────
  const meta: QuestionMetadata | undefined = msg.questionMetadata;

  return (
    <div className="flex w-full justify-start my-4 mt-2">
      <div
        className="w-8 h-8 rounded-full flex items-center justify-center text-[13px] font-bold text-white shrink-0 mr-4 mt-0.5 shadow-sm"
        style={{ background: "linear-gradient(135deg, #18181b, #09090b)" }}
        aria-hidden="true"
      >
        E
      </div>
      <div className="max-w-full flex-1">
        <div
          className="text-zinc-200 text-[16px] leading-[1.65] wrap-break-word whitespace-pre-wrap py-0.5 font-inter"
          aria-label="Assistant response"
        >
          {msg.content}
        </div>

        {/* Inline input widget — rendered only when questionMetadata is present */}
        {meta && onWidgetSubmit && (
          <>
            {meta.input_type === "dropdown" && (
              <DropdownWidget options={meta.options} onSelect={onWidgetSubmit} />
            )}
            {meta.input_type === "area_picker" && (
              <AreaPickerWidget
                presets={meta.presets}
                customUnits={meta.custom_units}
                onSelect={onWidgetSubmit}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}

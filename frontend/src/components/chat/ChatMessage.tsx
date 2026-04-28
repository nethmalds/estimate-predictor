import { Message } from "@/types/chat";
import { ExcelIcon } from "@/components/icons";
import { Download } from "lucide-react";

interface ChatMessageProps {
  msg: Message;
}

export function ChatMessage({ msg }: ChatMessageProps) {
  if (msg.role === "info") {
    return (
      <div className="flex w-full justify-center my-3" role="status">
        <div className="text-[12px] text-zinc-500 italic text-center px-4 py-1.5 bg-zinc-900 rounded-full">{msg.content}</div>
      </div>
    );
  }

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

  // assistant
  return (
    <div className="flex w-full justify-start my-4 mt-2">
      <div
        className="w-8 h-8 rounded-full flex items-center justify-center text-[13px] font-bold text-white shrink-0 mr-4 mt-0.5 shadow-sm"
        style={{ background: "linear-gradient(135deg, #18181b, #09090b)" }}
        aria-hidden="true"
      >
        E
      </div>
      <div className="max-w-full text-zinc-200 text-[16px] leading-[1.65] wrap-break-word whitespace-pre-wrap py-0.5 font-inter" aria-label="Assistant response">
        {msg.content}
      </div>
    </div>
  );
}

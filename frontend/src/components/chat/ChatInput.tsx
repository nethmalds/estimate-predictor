import { RefObject, FormEvent, ChangeEvent, KeyboardEvent } from "react";
import {
  Plus,
  ArrowUp,
  Mic,
  AudioLines,
  FileText,
  AlertTriangle,
  Check,
  X,
} from "lucide-react";
import { UploadState } from "@/types/chat";

interface ChatInputProps {
  input: string;
  setInput: (val: string) => void;
  isLoading: boolean;
  isUploading: boolean;
  uploadState: UploadState;
  clarificationSessionId: string | null;
  currentQuestion: string | null;
  textareaRef: RefObject<HTMLTextAreaElement | null>;
  fileInputRef: RefObject<HTMLInputElement | null>;
  handleSubmit: (e?: FormEvent) => void;
  handleKeyDown: (e: KeyboardEvent<HTMLTextAreaElement>) => void;
  handleFileChange: (e: ChangeEvent<HTMLInputElement>) => void;
  clearUpload: (deleteFromStorage?: boolean) => void;
  resizeTextarea: () => void;
}

export function ChatInput({
  input,
  setInput,
  isLoading,
  isUploading,
  uploadState,
  clarificationSessionId,
  currentQuestion,
  textareaRef,
  fileInputRef,
  handleSubmit,
  handleKeyDown,
  handleFileChange,
  clearUpload,
  resizeTextarea,
}: ChatInputProps) {
  const canSend = input.trim().length > 0 && !isLoading && !isUploading;

  return (
    <form onSubmit={handleSubmit} aria-label="Send a message" className="max-w-5xl mx-auto px-4 py-3">
      <div className="bg-[#2f2f2f] rounded-[28px] pl-4 pr-3 py-3 flex flex-col gap-2 focus-within:bg-[#363636] transition-colors">

        {/* File attachment preview */}
        {uploadState.status !== "idle" && uploadState.status !== "error" && (
          <div className="px-1">
            <div
              className="inline-flex items-center gap-2 bg-[#212121] border border-[#3e3e3e] rounded-[16px] py-1.5 px-2.5 max-w-65"
              role="status"
            >
              {uploadState.previewUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={uploadState.previewUrl}
                  alt="Preview"
                  className="w-8 h-8 rounded shrink-0 object-cover"
                />
              ) : (
                <div className="w-8 h-8 rounded bg-[#444] flex items-center justify-center text-zinc-400 shrink-0">
                  <FileText className="w-5 h-5" />
                </div>
              )}
              <span className="text-[13px] text-zinc-200 whitespace-nowrap overflow-hidden text-ellipsis max-w-37.5">
                {uploadState.fileName}
              </span>
              {uploadState.status === "uploading" && (
                <div className="w-3.5 h-3.5 border-2 border-zinc-500 border-t-white rounded-full animate-spin shrink-0" />
              )}
              {uploadState.status === "done" && (
                <Check className="w-4 h-4 text-green-400 shrink-0" />
              )}
              <button
                type="button"
                className="p-1 -mr-1 text-zinc-400 hover:text-white transition-colors"
                onClick={() => clearUpload(true)}
                disabled={uploadState.status === "uploading"}
                aria-label="Remove attachment"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {uploadState.status === "error" && (
          <div className="px-2 text-sm text-red-400 flex items-center gap-1.5">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{uploadState.message}</span>
          </div>
        )}

        {/* Main input row */}
        <div className="flex items-end gap-3 w-full">
          <input
            ref={fileInputRef as any}
            type="file"
            accept="image/*,.pdf"
            onChange={handleFileChange}
            className="hidden"
            id="floor-plan-file-input"
            disabled={isLoading || Boolean(clarificationSessionId)}
          />

          <button
            type="button"
            className="w-8 h-8 rounded-full text-[#8e8ea0] flex items-center justify-center shrink-0 hover:text-white hover:bg-[#3f3f3f] transition-colors border border-[#4a4a4a]"
            onClick={() => fileInputRef.current?.click()}
            disabled={
              isLoading ||
              Boolean(clarificationSessionId) ||
              uploadState.status === "uploading"
            }
            aria-label="Attach file"
          >
            <Plus className="w-5 h-5" />
          </button>

          <textarea
            ref={textareaRef as any}
            className="flex-1 bg-transparent border-none outline-none text-[#ececec] text-[15.5px] leading-[1.45] resize-none min-h-6 max-h-50 overflow-y-auto placeholder:text-[#8e8ea0] mb-0.5"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onInput={resizeTextarea}
            placeholder={currentQuestion ? "Type your answer…" : "Ask anything"}
            disabled={isLoading}
            rows={1}
            aria-label="Message input"
          />

          <div className="flex items-center gap-1 pb-0.5 shrink-0">
            {input.trim().length === 0 && !isUploading ? (
              <>
                <button
                  type="button"
                  className="w-8 h-8 rounded-full flex items-center justify-center text-[#8e8ea0] hover:bg-[#3f3f3f] hover:text-white transition-colors"
                  aria-label="Voice input"
                >
                  <Mic className="w-5 h-5" />
                </button>
                <button
                  type="button"
                  className="w-8 h-8 rounded-full flex items-center justify-center text-[#8e8ea0] border border-[#4a4a4a] hover:bg-[#3f3f3f] hover:text-white transition-colors"
                  aria-label="Audio"
                >
                  <AudioLines className="w-5 h-5" />
                </button>
              </>
            ) : (
              <button
                type="submit"
                className="w-8 h-8 rounded-full bg-white text-[#2f2f2f] flex items-center justify-center shrink-0 transition-all hover:bg-zinc-200 disabled:bg-[#4d4d4d] disabled:text-[#888] disabled:cursor-not-allowed"
                disabled={!canSend}
                aria-label="Send message"
              >
                <ArrowUp className="w-5 h-5" strokeWidth={2.5} />
              </button>
            )}
          </div>
        </div>
      </div>
    </form>
  );
}

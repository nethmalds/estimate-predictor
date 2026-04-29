export type MessageRole = "user" | "assistant" | "info" | "excel";

export type ExcelPreviewRow = { description: string; unit: string; quantity: number; rate: number; cost: number };

export type Message = {
  role: MessageRole;
  content: string;
  excelUrl?: string;
  fileName?: string;
  excelPreview?: ExcelPreviewRow[];
  excelTotal?: number;
};

export type UploadState =
  | { status: "idle" }
  | { status: "uploading"; fileName: string; previewUrl: string | null }
  | { status: "done"; fileName: string; previewUrl: string | null; url: string; fileKey: string }
  | { status: "error"; message: string };

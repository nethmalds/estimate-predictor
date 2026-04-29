export type MessageRole = "user" | "assistant" | "info" | "excel" | "validation_error";

export type ExcelPreviewRow = { description: string; unit: string; quantity: number; rate: number; cost: number };

/** Metadata attached to a question message — tells the frontend which input widget to render. */
export type QuestionMetadata =
  | { input_type: "text" }
  | { input_type: "dropdown"; options: { value: string; label: string }[] }
  | {
      input_type: "area_picker";
      presets: { value: string; label: string }[];
      allow_custom: boolean;
      custom_units: string[];
    };

export type Message = {
  role: MessageRole;
  content: string;
  excelUrl?: string;
  fileName?: string;
  excelPreview?: ExcelPreviewRow[];
  excelTotal?: number;
  /** Field name this question is about (e.g. "floors", "finish_level") */
  questionField?: string;
  /** Widget metadata emitted by the backend for question messages */
  questionMetadata?: QuestionMetadata;
};

export type UploadState =
  | { status: "idle" }
  | { status: "uploading"; fileName: string; previewUrl: string | null }
  | { status: "done"; fileName: string; previewUrl: string | null; url: string; fileKey: string }
  | { status: "error"; message: string };

"use client";

import { BuildingType, ProjectBasics } from "@/types/wizard";
import {
  Building2,
  Factory,
  Layers,
  Home,
  UploadCloud,
  X,
  FileText,
  ImageIcon,
  Loader2,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import { useUploadThing } from "@/lib/uploadthing";
import { useState, useCallback, useRef, useEffect } from "react";

interface Props {
  data: ProjectBasics;
  onChange: (data: ProjectBasics) => void;
  errors: Record<string, string>;
  uploadEntries: FileEntry[];
  onUploadEntriesChange: (entries: FileEntry[]) => void;
}

const BUILDING_TYPES: {
  value: BuildingType;
  label: string;
  icon: React.ReactNode;
  description: string;
}[] = [
  {
    value: "residential",
    label: "Residential",
    icon: <Home className="h-6 w-6" />,
    description: "Houses, apartments, villas",
  },
  {
    value: "commercial",
    label: "Commercial",
    icon: <Building2 className="h-6 w-6" />,
    description: "Offices, shops, hotels",
  },
  {
    value: "industrial",
    label: "Industrial",
    icon: <Factory className="h-6 w-6" />,
    description: "Factories, warehouses",
  },
];

export interface FileEntry {
  id: string;
  file: File;
  status: "pending" | "uploading" | "done" | "error";
  url?: string;
  fileKey?: string; // UploadThing key extracted from ufsUrl – needed for deletion
  previewUrl?: string;
}

function isImage(file: File) {
  return file.type.startsWith("image/");
}

function fileSizeLabel(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ProjectBasicsStep({ data, onChange, errors, uploadEntries, onUploadEntriesChange }: Props) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  // Keep a ref to uploadEntries for safe access inside async callbacks
  const fileEntriesRef = useRef<FileEntry[]>(uploadEntries);
  useEffect(() => {
    fileEntriesRef.current = uploadEntries;
  }, [uploadEntries]);

  const { startUpload } = useUploadThing("floorplanUploader", {
    onClientUploadComplete: (res) => {
      if (!res) return;
      // res items are matched positionally per startUpload call – handled in uploadFiles
    },
    onUploadError: () => {},
  });

  const uploadFiles = useCallback(
    async (newEntries: FileEntry[], snapshot?: FileEntry[]) => {
      const toUpload = newEntries.filter((e) => e.status === "pending");
      if (!toUpload.length) return;

      // Mark all as uploading. Use `snapshot` when provided — addFiles passes
      // the combined array because fileEntriesRef hasn't updated yet at that
      // point (useEffect runs after render, but this runs synchronously before).
      const base = snapshot ?? fileEntriesRef.current;
      onUploadEntriesChange(
        base.map((e) =>
          toUpload.find((u) => u.id === e.id) ? { ...e, status: "uploading" } : e
        )
      );

      try {
        const res = await startUpload(toUpload.map((e) => e.file));
        if (!res) throw new Error("No response");

        // Use ref to get latest entries after async call completes
        const nextEntries = fileEntriesRef.current.map((e) => {
          const idx = toUpload.findIndex((u) => u.id === e.id);
          if (idx === -1) return e;
          const uploaded = res[idx];
          const url = uploaded?.ufsUrl;
          // Extract the file key from the URL: last path segment
          const fileKey = url ? url.split("/").pop() : undefined;
          return url
            ? { ...e, status: "done" as const, url, fileKey }
            : { ...e, status: "error" as const };
        });
        onUploadEntriesChange(nextEntries);

        // Sync completed URLs to parent data
        const allDoneUrls = nextEntries
          .filter((e) => e.status === "done" && e.url)
          .map((e) => e.url as string);
        onChange({ ...data, floorplan_urls: allDoneUrls });
      } catch {
        onUploadEntriesChange(
          fileEntriesRef.current.map((e) =>
            toUpload.find((u) => u.id === e.id) ? { ...e, status: "error" as const } : e
          )
        );
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [startUpload, data, onChange, onUploadEntriesChange]
  );

  const addFiles = useCallback(
    (files: FileList | File[]) => {
      const arr = Array.from(files);
      const valid = arr.filter((f) => f.type.startsWith("image/") || f.type === "application/pdf");
      if (!valid.length) return;

      const newEntries: FileEntry[] = valid.map((f) => ({
        id: crypto.randomUUID(),
        file: f,
        status: "pending",
        previewUrl: isImage(f) ? URL.createObjectURL(f) : undefined,
      }));

      const combined = [...fileEntriesRef.current, ...newEntries];
      onUploadEntriesChange(combined);

      // Pass combined as snapshot — ref is stale at this point and uploadFiles
      // would otherwise overwrite state back to the old entries.
      void uploadFiles(newEntries, combined);
    },
    [uploadFiles, onUploadEntriesChange]
  );

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) addFiles(e.target.files);
    // Reset input so same file can be re-selected if deleted
    e.target.value = "";
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };
  const handleDragLeave = () => setIsDragging(false);
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    addFiles(e.dataTransfer.files);
  };

  const removeFile = (id: string) => {
    const entry = fileEntriesRef.current.find((e) => e.id === id);
    if (!entry) return;

    // Revoke blob URL to free memory
    if (entry.previewUrl) URL.revokeObjectURL(entry.previewUrl);

    // Call the delete API for successfully uploaded files
    if (entry.status === "done" && entry.fileKey) {
      fetch("/api/uploadthing/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fileKey: entry.fileKey }),
      }).catch((err) => console.error("Failed to delete file from UploadThing:", err));
    }

    const next = fileEntriesRef.current.filter((e) => e.id !== id);
    const allDoneUrls = next
      .filter((e) => e.status === "done" && e.url)
      .map((e) => e.url as string);
    onUploadEntriesChange(next);
    onChange({ ...data, floorplan_urls: allDoneUrls });
  };

  const retryFile = (id: string) => {
    const entry = fileEntriesRef.current.find((e) => e.id === id);
    if (!entry) return;
    const reset: FileEntry = { ...entry, status: "pending" };
    onUploadEntriesChange(fileEntriesRef.current.map((e) => (e.id === id ? reset : e)));
    void uploadFiles([reset]);
  };

  return (
    <div className="space-y-8">
      {/* Building Type */}
      <div>
        <label className="text-foreground mb-3 block text-sm font-medium">
          Building Type <span className="text-destructive">*</span>
        </label>
        <div className="grid grid-cols-2 gap-3">
          {BUILDING_TYPES.map((bt) => (
            <button
              key={bt.value}
              type="button"
              onClick={() => onChange({ ...data, building_type: bt.value })}
              className={`flex items-start gap-3 rounded-lg border p-4 text-left transition-all ${
                data.building_type === bt.value
                  ? "text-foreground border-blue-500 bg-blue-50 shadow-sm"
                  : "border-border bg-card text-foreground hover:border-primary/40 hover:bg-accent/30"
              }`}
            >
              <span
                className={
                  data.building_type === bt.value ? "text-blue-500" : "text-muted-foreground"
                }
              >
                {bt.icon}
              </span>
              <div>
                <div className="text-sm font-medium">{bt.label}</div>
                <div className="text-muted-foreground mt-0.5 text-xs">{bt.description}</div>
              </div>
            </button>
          ))}
        </div>
        {errors.building_type && (
          <p className="text-destructive mt-1 text-xs">{errors.building_type}</p>
        )}
      </div>

      {/* Floor Count */}
      <div>
        <label className="text-foreground mb-2 block text-sm font-medium">
          Number of Floors <span className="text-destructive">*</span>
        </label>
        <input
          type="number"
          min={1}
          max={100}
          value={data.floor_count}
          onChange={(e) =>
            onChange({
              ...data,
              floor_count: e.target.value === "" ? "" : parseInt(e.target.value),
            })
          }
          placeholder="e.g. 2"
          className="bg-background border-input text-foreground focus:ring-ring w-32 rounded-lg border px-3 py-2 focus:ring-2 focus:outline-none"
        />
        {errors.floor_count && (
          <p className="text-destructive mt-1 text-xs">{errors.floor_count}</p>
        )}
      </div>

      {/* Description */}
      <div>
        <label className="text-foreground mb-2 block text-sm font-medium">
          Project Description <span className="text-muted-foreground text-xs">(optional)</span>
        </label>
        <textarea
          value={data.description}
          onChange={(e) => onChange({ ...data, description: e.target.value })}
          placeholder="Brief description of the project..."
          rows={3}
          className="bg-background border-input text-foreground focus:ring-ring placeholder:text-muted-foreground w-full resize-none rounded-lg border px-3 py-2 focus:ring-2 focus:outline-none"
        />
      </div>

      {/* Floorplan Upload — drag-and-drop multi-file */}
      <div>
        <label className="text-foreground mb-2 block text-sm font-medium">
          Floor Plan Documents{" "}
          <span className="text-muted-foreground text-xs">
            (optional · images &amp; PDFs · up to 10)
          </span>
        </label>

        {/* Drop Zone */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className={`relative flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-6 transition-all select-none ${
            isDragging
              ? "scale-[1.01] border-blue-400 bg-blue-500/10"
              : "border-border bg-muted/30 hover:border-primary/40 hover:bg-muted/50"
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept="image/*,.pdf"
            multiple
            onChange={handleInputChange}
            className="hidden"
          />
          <UploadCloud
            className={`h-8 w-8 transition-colors ${isDragging ? "text-blue-400" : "text-muted-foreground"}`}
          />
          <p className="text-foreground text-sm font-medium">
            {isDragging ? "Drop files here" : "Drag & drop files, or click to browse"}
          </p>
          <p className="text-muted-foreground text-xs">
            Supports PNG, JPG, WEBP, PDF — max 8 MB each
          </p>
        </div>

        {/* File List */}
        {uploadEntries.length > 0 && (
          <ul className="mt-3 space-y-2">
            {uploadEntries.map((entry) => (
              <li
                key={entry.id}
                className="bg-muted/50 border-border flex items-center gap-3 rounded-lg border p-3"
              >
                {/* Thumbnail or PDF icon */}
                {entry.previewUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={entry.previewUrl}
                    alt={entry.file.name}
                    className="border-border h-10 w-10 shrink-0 rounded-md border object-cover"
                  />
                ) : (
                  <div className="bg-muted border-border flex h-10 w-10 shrink-0 items-center justify-center rounded-md border">
                    <FileText className="text-muted-foreground h-5 w-5" />
                  </div>
                )}

                {/* Info */}
                <div className="min-w-0 flex-1">
                  <p className="text-foreground truncate text-sm font-medium">{entry.file.name}</p>
                  <div className="mt-0.5 flex items-center gap-2">
                    <span className="text-muted-foreground text-xs">
                      {fileSizeLabel(entry.file.size)}
                    </span>
                    {entry.status === "uploading" && (
                      <span className="flex items-center gap-1 text-xs text-blue-500">
                        <Loader2 className="h-3 w-3 animate-spin" /> Uploading…
                      </span>
                    )}
                    {entry.status === "done" && (
                      <span className="flex items-center gap-1 text-xs text-emerald-500">
                        <CheckCircle2 className="h-3 w-3" /> Uploaded
                      </span>
                    )}
                    {entry.status === "error" && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          retryFile(entry.id);
                        }}
                        className="text-destructive hover:text-destructive/80 flex items-center gap-1 text-xs transition-colors"
                      >
                        <AlertCircle className="h-3 w-3" /> Failed — retry
                      </button>
                    )}
                    {entry.status === "pending" && (
                      <span className="text-muted-foreground text-xs">Queued…</span>
                    )}
                  </div>
                </div>

                {/* File type badge */}
                <div className="shrink-0">
                  {isImage(entry.file) ? (
                    <ImageIcon className="text-muted-foreground h-4 w-4" />
                  ) : (
                    <FileText className="text-muted-foreground h-4 w-4" />
                  )}
                </div>

                {/* Delete */}
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    removeFile(entry.id);
                  }}
                  className="text-muted-foreground hover:text-destructive hover:bg-destructive/10 shrink-0 rounded-md p-1 transition-colors"
                  title="Remove file"
                >
                  <X className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

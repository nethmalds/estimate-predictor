"use client";

import { BuildingType, ProjectBasics } from "@/types/wizard";
import { Building2, Factory, Layers, Home, UploadCloud, X, FileText, ImageIcon, Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { useUploadThing } from "@/lib/uploadthing";
import { useState, useCallback, useRef } from "react";

interface Props {
  data: ProjectBasics;
  onChange: (data: ProjectBasics) => void;
  errors: Record<string, string>;
}

const BUILDING_TYPES: { value: BuildingType; label: string; icon: React.ReactNode; description: string }[] = [
  { value: "residential", label: "Residential", icon: <Home className="w-6 h-6" />, description: "Houses, apartments, villas" },
  { value: "commercial",  label: "Commercial",  icon: <Building2 className="w-6 h-6" />, description: "Offices, shops, hotels" },
  { value: "industrial",  label: "Industrial",  icon: <Factory className="w-6 h-6" />, description: "Factories, warehouses" },
];

interface FileEntry {
  id: string;
  file: File;
  status: "pending" | "uploading" | "done" | "error";
  url?: string;
  fileKey?: string;   // UploadThing key extracted from ufsUrl – needed for deletion
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

export function ProjectBasicsStep({ data, onChange, errors }: Props) {
  const [fileEntries, setFileEntries] = useState<FileEntry[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const { startUpload } = useUploadThing("floorplanUploader", {
    onClientUploadComplete: (res) => {
      if (!res) return;
      // res items are matched positionally per startUpload call – handled in uploadFiles
    },
    onUploadError: () => {},
  });

  const uploadFiles = useCallback(
    async (newEntries: FileEntry[]) => {
      const toUpload = newEntries.filter((e) => e.status === "pending");
      if (!toUpload.length) return;

      // Mark all as uploading
      setFileEntries((prev) =>
        prev.map((e) =>
          toUpload.find((u) => u.id === e.id) ? { ...e, status: "uploading" } : e
        )
      );

      try {
        const res = await startUpload(toUpload.map((e) => e.file));
        if (!res) throw new Error("No response");

        // Compute next entries outside the setter so we can call onChange separately
        let nextEntries: FileEntry[] = [];
        setFileEntries((prev) => {
          nextEntries = prev.map((e) => {
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
          return nextEntries;
        });

        // Sync completed URLs to parent — must be outside the setter
        const allDoneUrls = nextEntries
          .filter((e) => e.status === "done" && e.url)
          .map((e) => e.url as string);
        onChange({ ...data, floorplan_urls: allDoneUrls });
      } catch {
        setFileEntries((prev) =>
          prev.map((e) =>
            toUpload.find((u) => u.id === e.id) ? { ...e, status: "error" as const } : e
          )
        );
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [startUpload, data, onChange]
  );

  const addFiles = useCallback(
    (files: FileList | File[]) => {
      const arr = Array.from(files);
      const valid = arr.filter(
        (f) =>
          f.type.startsWith("image/") || f.type === "application/pdf"
      );
      if (!valid.length) return;

      const newEntries: FileEntry[] = valid.map((f) => ({
        id: crypto.randomUUID(),
        file: f,
        status: "pending",
        previewUrl: isImage(f) ? URL.createObjectURL(f) : undefined,
      }));

      setFileEntries((prev) => {
        const combined = [...prev, ...newEntries];
        return combined;
      });

      // Kick off upload after state is flushed
      void uploadFiles(newEntries);
    },
    [uploadFiles]
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
    const entry = fileEntries.find((e) => e.id === id);
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

    const next = fileEntries.filter((e) => e.id !== id);
    const allDoneUrls = next
      .filter((e) => e.status === "done" && e.url)
      .map((e) => e.url as string);
    setFileEntries(next);
    onChange({ ...data, floorplan_urls: allDoneUrls });
  };

  const retryFile = (id: string) => {
    const entry = fileEntries.find((e) => e.id === id);
    if (!entry) return;
    const reset: FileEntry = { ...entry, status: "pending" };
    setFileEntries((prev) => prev.map((e) => (e.id === id ? reset : e)));
    void uploadFiles([reset]);
  };

  return (
    <div className="space-y-8">
      {/* Building Type */}
      <div>
        <label className="block text-sm font-medium text-zinc-300 mb-3">
          Building Type <span className="text-red-400">*</span>
        </label>
        <div className="grid grid-cols-2 gap-3">
          {BUILDING_TYPES.map((bt) => (
            <button
              key={bt.value}
              type="button"
              onClick={() => onChange({ ...data, building_type: bt.value })}
              className={`flex items-start gap-3 p-4 rounded-lg border text-left transition-colors ${
                data.building_type === bt.value
                  ? "border-blue-500 bg-blue-600/10 text-zinc-100"
                  : "border-zinc-700 bg-zinc-800 text-zinc-300 hover:border-zinc-500"
              }`}
            >
              <span className={data.building_type === bt.value ? "text-blue-400" : "text-zinc-400"}>
                {bt.icon}
              </span>
              <div>
                <div className="font-medium text-sm">{bt.label}</div>
                <div className="text-xs text-zinc-400 mt-0.5">{bt.description}</div>
              </div>
            </button>
          ))}
        </div>
        {errors.building_type && (
          <p className="mt-1 text-xs text-red-400">{errors.building_type}</p>
        )}
      </div>

      {/* Floor Count */}
      <div>
        <label className="block text-sm font-medium text-zinc-300 mb-2">
          Number of Floors <span className="text-red-400">*</span>
        </label>
        <input
          type="number"
          min={1}
          max={100}
          value={data.floor_count}
          onChange={(e) => onChange({ ...data, floor_count: e.target.value === "" ? "" : parseInt(e.target.value) })}
          placeholder="e.g. 2"
          className="w-32 bg-zinc-800 border border-zinc-700 text-zinc-100 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        {errors.floor_count && (
          <p className="mt-1 text-xs text-red-400">{errors.floor_count}</p>
        )}
      </div>

      {/* Description */}
      <div>
        <label className="block text-sm font-medium text-zinc-300 mb-2">
          Project Description <span className="text-zinc-500 text-xs">(optional)</span>
        </label>
        <textarea
          value={data.description}
          onChange={(e) => onChange({ ...data, description: e.target.value })}
          placeholder="Brief description of the project..."
          rows={3}
          className="w-full bg-zinc-800 border border-zinc-700 text-zinc-100 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none placeholder:text-zinc-500"
        />
      </div>

      {/* Floorplan Upload — drag-and-drop multi-file */}
      <div>
        <label className="block text-sm font-medium text-zinc-300 mb-2">
          Floor Plan Documents{" "}
          <span className="text-zinc-500 text-xs">(optional · images &amp; PDFs · up to 10)</span>
        </label>

        {/* Drop Zone */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className={`relative flex flex-col items-center justify-center gap-2 p-6 rounded-xl border-2 border-dashed cursor-pointer transition-all select-none ${
            isDragging
              ? "border-blue-400 bg-blue-500/10 scale-[1.01]"
              : "border-zinc-600 bg-zinc-800/60 hover:border-zinc-400 hover:bg-zinc-800"
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
            className={`w-8 h-8 transition-colors ${isDragging ? "text-blue-400" : "text-zinc-500"}`}
          />
          <p className="text-sm font-medium text-zinc-300">
            {isDragging ? "Drop files here" : "Drag & drop files, or click to browse"}
          </p>
          <p className="text-xs text-zinc-500">Supports PNG, JPG, WEBP, PDF — max 8 MB each</p>
        </div>

        {/* File List */}
        {fileEntries.length > 0 && (
          <ul className="mt-3 space-y-2">
            {fileEntries.map((entry) => (
              <li
                key={entry.id}
                className="flex items-center gap-3 p-3 bg-zinc-800 border border-zinc-700 rounded-lg"
              >
                {/* Thumbnail or PDF icon */}
                {entry.previewUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={entry.previewUrl}
                    alt={entry.file.name}
                    className="w-10 h-10 object-cover rounded-md shrink-0 border border-zinc-700"
                  />
                ) : (
                  <div className="w-10 h-10 flex items-center justify-center rounded-md bg-zinc-700 shrink-0 border border-zinc-600">
                    <FileText className="w-5 h-5 text-zinc-400" />
                  </div>
                )}

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-zinc-200 truncate font-medium">{entry.file.name}</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-xs text-zinc-500">{fileSizeLabel(entry.file.size)}</span>
                    {entry.status === "uploading" && (
                      <span className="flex items-center gap-1 text-xs text-blue-400">
                        <Loader2 className="w-3 h-3 animate-spin" /> Uploading…
                      </span>
                    )}
                    {entry.status === "done" && (
                      <span className="flex items-center gap-1 text-xs text-emerald-400">
                        <CheckCircle2 className="w-3 h-3" /> Uploaded
                      </span>
                    )}
                    {entry.status === "error" && (
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); retryFile(entry.id); }}
                        className="flex items-center gap-1 text-xs text-red-400 hover:text-red-300 transition-colors"
                      >
                        <AlertCircle className="w-3 h-3" /> Failed — retry
                      </button>
                    )}
                    {entry.status === "pending" && (
                      <span className="text-xs text-zinc-500">Queued…</span>
                    )}
                  </div>
                </div>

                {/* File type badge */}
                <div className="shrink-0">
                  {isImage(entry.file) ? (
                    <ImageIcon className="w-4 h-4 text-zinc-500" />
                  ) : (
                    <FileText className="w-4 h-4 text-zinc-500" />
                  )}
                </div>

                {/* Delete */}
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); removeFile(entry.id); }}
                  className="shrink-0 p-1 rounded-md text-zinc-500 hover:text-red-400 hover:bg-red-400/10 transition-colors"
                  title="Remove file"
                >
                  <X className="w-4 h-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

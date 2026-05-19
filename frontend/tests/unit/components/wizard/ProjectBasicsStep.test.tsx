import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockStartUpload = vi.fn();
vi.mock("@/lib/uploadthing", () => ({
  useUploadThing: () => ({
    startUpload: mockStartUpload,
  }),
}));

vi.mock("next/image", () => ({
  default: ({
    src,
    alt,
    ...props
  }: {
    src: string;
    alt: string;
    [key: string]: unknown;
  }) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt={alt} {...(props as Record<string, unknown>)} />
  ),
}));

vi.stubGlobal("URL", {
  ...URL,
  createObjectURL: vi.fn(() => "blob:mock-url"),
  revokeObjectURL: vi.fn(),
});

vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));

// ── Component import ─────────────────────────────────────────────────────────

import {
  ProjectBasicsStep,
  type FileEntry,
} from "@/components/wizard/steps/ProjectBasicsStep";
import type { ProjectBasics } from "@/types/wizard";

// ── Helpers ───────────────────────────────────────────────────────────────────

let uuidCounter = 0;
vi.spyOn(crypto, "randomUUID").mockImplementation(
  () =>
    `test-uuid-${++uuidCounter}` as `${string}-${string}-${string}-${string}-${string}`
);

function makeDefaultData(): ProjectBasics {
  return {
    building_type: "",
    floor_count: "",
    description: "",
    floorplan_urls: [],
  };
}

function renderStep(overrides?: {
  data?: Partial<ProjectBasics>;
  onChange?: ReturnType<typeof vi.fn>;
  errors?: Record<string, string>;
  uploadEntries?: FileEntry[];
  onUploadEntriesChange?: ReturnType<typeof vi.fn>;
}) {
  const onChange = overrides?.onChange ?? vi.fn();
  const onUploadEntriesChange =
    overrides?.onUploadEntriesChange ?? vi.fn();
  const uploadEntries = overrides?.uploadEntries ?? [];
  const data = { ...makeDefaultData(), ...(overrides?.data ?? {}) };
  const errors = overrides?.errors ?? {};

  render(
    <ProjectBasicsStep
      data={data}
      onChange={onChange}
      errors={errors}
      uploadEntries={uploadEntries}
      onUploadEntriesChange={onUploadEntriesChange}
    />
  );

  return { onChange, onUploadEntriesChange };
}

// ── Tests ─────────────────────────────────────────────────────────────────────

beforeEach(() => {
  uuidCounter = 0;
  mockStartUpload.mockReset();
});

// ── Group 1: Building type selection ─────────────────────────────────────────

describe("Building type selection", () => {
  it("renders all three building type buttons", () => {
    renderStep();
    expect(screen.getByText("Residential")).toBeInTheDocument();
    expect(screen.getByText("Commercial")).toBeInTheDocument();
    expect(screen.getByText("Industrial")).toBeInTheDocument();
  });

  it("calls onChange with building_type when a type is clicked", async () => {
    const { onChange } = renderStep();
    await userEvent.click(screen.getByText("Commercial"));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ building_type: "commercial" })
    );
  });

  it("highlights the selected building type", () => {
    renderStep({ data: { building_type: "residential" } });
    const residentialButton = screen.getByText("Residential").closest("button");
    expect(residentialButton).toHaveClass("border-blue-500");
  });
});

// ── Group 2: Floor count and description ─────────────────────────────────────

describe("Floor count and description", () => {
  it("renders floor count input", () => {
    renderStep();
    const input = screen.getByPlaceholderText("e.g. 2");
    expect(input).toBeInTheDocument();
    expect(input).toHaveAttribute("type", "number");
  });

  it("calls onChange with floor_count when input changes", async () => {
    const { onChange } = renderStep();
    const input = screen.getByPlaceholderText("e.g. 2");
    await userEvent.clear(input);
    await userEvent.type(input, "3");
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ floor_count: 3 })
    );
  });

  it("renders description textarea", () => {
    renderStep();
    const textarea = screen.getByPlaceholderText(
      "Brief description of the project..."
    );
    expect(textarea).toBeInTheDocument();
  });

  it("shows error message when errors.floor_count is set", () => {
    renderStep({ errors: { floor_count: "Floor count is required" } });
    expect(screen.getByText("Floor count is required")).toBeInTheDocument();
  });
});

// ── Group 3: Upload drop zone ─────────────────────────────────────────────────

describe("Upload drop zone", () => {
  it("renders the file upload drop zone", () => {
    renderStep();
    expect(
      screen.getByText("Drag & drop files, or click to browse")
    ).toBeInTheDocument();
  });

  it("renders file list when uploadEntries has items", () => {
    const entry: FileEntry = {
      id: "entry-1",
      file: new File(["data"], "floor-plan.png", { type: "image/png" }),
      status: "done",
      url: "https://example.com/floor-plan.png",
    };
    renderStep({ uploadEntries: [entry] });
    expect(screen.getByText("floor-plan.png")).toBeInTheDocument();
    expect(screen.getByText("Uploaded")).toBeInTheDocument();
  });

  it("shows uploading spinner for uploading entries", () => {
    const entry: FileEntry = {
      id: "entry-2",
      file: new File(["data"], "uploading.png", { type: "image/png" }),
      status: "uploading",
    };
    renderStep({ uploadEntries: [entry] });
    expect(screen.getByText("Uploading…")).toBeInTheDocument();
  });

  it("shows uploaded checkmark for done entries", () => {
    const entry: FileEntry = {
      id: "entry-3",
      file: new File(["data"], "done.png", { type: "image/png" }),
      status: "done",
      url: "https://example.com/done.png",
    };
    renderStep({ uploadEntries: [entry] });
    expect(screen.getByText("Uploaded")).toBeInTheDocument();
  });

  it("shows error/retry for error entries", () => {
    const entry: FileEntry = {
      id: "entry-4",
      file: new File(["data"], "failed.png", { type: "image/png" }),
      status: "error",
    };
    renderStep({ uploadEntries: [entry] });
    expect(screen.getByText("Failed — retry")).toBeInTheDocument();
  });
});

// ── Group 4: File add → onUploadEntriesChange called ─────────────────────────

describe("File add triggers onUploadEntriesChange", () => {
  it("adds files via input onChange and calls onUploadEntriesChange with a pending entry", async () => {
    // Keep startUpload pending so it doesn't trigger further state changes
    mockStartUpload.mockResolvedValue([
      { ufsUrl: "https://example.com/test.png" },
    ]);

    const { onUploadEntriesChange } = renderStep();

    const file = new File(["content"], "test.png", { type: "image/png" });
    const input = document
      .querySelector('input[type="file"]') as HTMLInputElement;

    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(onUploadEntriesChange).toHaveBeenCalled();
    });

    const firstCall = onUploadEntriesChange.mock.calls[0][0] as FileEntry[];
    const pendingEntry = firstCall.find((e) => e.file.name === "test.png");
    expect(pendingEntry).toBeDefined();
    expect(pendingEntry?.status).toBe("pending");
  });
});

// ── Group 5: Remove file ──────────────────────────────────────────────────────

describe("Remove file", () => {
  it("remove button calls onUploadEntriesChange without the removed entry and clears floorplan_urls", async () => {
    const entry: FileEntry = {
      id: "entry-done",
      file: new File(["data"], "remove-me.png", { type: "image/png" }),
      status: "done",
      url: "https://example.com/remove-me.png",
      fileKey: "remove-me",
    };

    const { onChange, onUploadEntriesChange } = renderStep({
      uploadEntries: [entry],
      data: { floorplan_urls: ["https://example.com/remove-me.png"] },
    });

    const removeButton = screen.getByTitle("Remove file");
    await userEvent.click(removeButton);

    expect(onUploadEntriesChange).toHaveBeenCalledWith([]);
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ floorplan_urls: [] })
    );
  });
});

// ── Group 6: Controlled prop — uploadEntries drives render ───────────────────

describe("Controlled prop — uploadEntries drives render", () => {
  it("shows file list from uploadEntries prop (not local state)", () => {
    const entry: FileEntry = {
      id: "controlled-1",
      file: new File(["x"], "controlled.pdf", {
        type: "application/pdf",
      }),
      status: "done",
      url: "https://example.com/controlled.pdf",
    };
    renderStep({ uploadEntries: [entry] });
    expect(screen.getByText("controlled.pdf")).toBeInTheDocument();
    expect(screen.getByText("Uploaded")).toBeInTheDocument();
  });
});

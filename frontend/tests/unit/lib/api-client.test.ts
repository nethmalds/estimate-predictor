/**
 * Unit tests for the centralized API client.
 *
 * fetch is stubbed with vi.stubGlobal so no real network calls occur.
 * Tests cover: success path, 4xx error extraction, 204 no-content, FormData,
 * and all error envelope shapes the backend emits.
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { apiClient, buildBackendUrl } from "@/lib/api-client";
import { ApiError } from "@/types/api";

// ── Helpers ───────────────────────────────────────────────────────────────────

function mockFetch(status: number, body: unknown, headers?: Record<string, string>) {
  const responseHeaders = new Headers({ "Content-Type": "application/json", ...headers });
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: status >= 200 && status < 300,
      status,
      statusText: "OK",
      headers: responseHeaders,
      json: () => Promise.resolve(body),
    })
  );
}

function mockFetchNetworkError() {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

// ── Success path ──────────────────────────────────────────────────────────────

describe("apiClient.get", () => {
  it("returns parsed JSON on 200", async () => {
    mockFetch(200, { id: "abc", name: "Test" });
    const result = await apiClient.get<{ id: string; name: string }>("/api/estimates", "token");
    expect(result.id).toBe("abc");
    expect(result.name).toBe("Test");
  });

  it("sends Authorization header when token provided", async () => {
    const spy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      headers: new Headers(),
      json: () => Promise.resolve({}),
    });
    vi.stubGlobal("fetch", spy);

    await apiClient.get("/api/estimates", "my-token");

    const [, init] = spy.mock.calls[0];
    expect(init.headers["Authorization"]).toBe("Bearer my-token");
  });

  it("does not send Authorization header when token is absent", async () => {
    const spy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      headers: new Headers(),
      json: () => Promise.resolve({}),
    });
    vi.stubGlobal("fetch", spy);

    await apiClient.get("/api/health");

    const [, init] = spy.mock.calls[0];
    expect(init.headers["Authorization"]).toBeUndefined();
  });

  it("returns undefined on 204 No Content", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 204,
        statusText: "No Content",
        headers: new Headers(),
        json: () => Promise.resolve(null),
      })
    );
    const result = await apiClient.get("/api/nothing");
    expect(result).toBeUndefined();
  });
});

// ── Error handling ────────────────────────────────────────────────────────────

describe("error extraction", () => {
  it("extracts body.detail string", async () => {
    mockFetch(404, { detail: "Estimate not found." });
    await expect(apiClient.get("/api/estimates/bad-id", "t")).rejects.toMatchObject({
      message: "Estimate not found.",
      status: 404,
    });
  });

  it("extracts body.detail.message object", async () => {
    mockFetch(422, { detail: { message: "Validation failed", errors: {} } });
    await expect(apiClient.post("/api/form/submit", {}, "t")).rejects.toMatchObject({
      message: "Validation failed",
      status: 422,
    });
  });

  it("extracts body.error.message", async () => {
    mockFetch(500, { error: { message: "Internal server error" } });
    await expect(apiClient.get("/api/x", "t")).rejects.toMatchObject({
      message: "Internal server error",
      status: 500,
    });
  });

  it("extracts first item from detail array", async () => {
    mockFetch(422, { detail: [{ msg: "field required", loc: ["body", "building_type"] }] });
    await expect(apiClient.post("/api/form/submit", {}, "t")).rejects.toMatchObject({
      message: "field required",
      status: 422,
    });
  });

  it("falls back to HTTP status string when body is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        statusText: "Service Unavailable",
        headers: new Headers(),
        json: () => Promise.reject(new SyntaxError("not JSON")),
      })
    );
    await expect(apiClient.get("/api/x")).rejects.toMatchObject({
      status: 503,
    });
  });

  it("throws ApiError instance", async () => {
    mockFetch(401, { detail: "Unauthorized" });
    const err = await apiClient.get("/api/x").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
  });

  it("propagates network failure", async () => {
    mockFetchNetworkError();
    await expect(apiClient.get("/api/x")).rejects.toThrow("Failed to fetch");
  });
});

// ── HTTP methods ──────────────────────────────────────────────────────────────

describe("apiClient methods", () => {
  it("post sends Content-Type application/json with body", async () => {
    const spy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      headers: new Headers(),
      json: () => Promise.resolve({ ok: true }),
    });
    vi.stubGlobal("fetch", spy);

    await apiClient.post("/api/form/submit", { floor_count: 2 }, "token");

    const [, init] = spy.mock.calls[0];
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(init.body).toBe(JSON.stringify({ floor_count: 2 }));
  });

  it("postForm does not set Content-Type (browser sets multipart boundary)", async () => {
    const spy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      headers: new Headers(),
      json: () => Promise.resolve({ ok: true }),
    });
    vi.stubGlobal("fetch", spy);

    const fd = new FormData();
    fd.append("file", new Blob(["data"]), "test.pdf");
    await apiClient.postForm("/api/upload", fd, "token");

    const [, init] = spy.mock.calls[0];
    expect(init.headers["Content-Type"]).toBeUndefined();
    expect(init.body).toBeInstanceOf(FormData);
  });
});

// ── buildBackendUrl ───────────────────────────────────────────────────────────

describe("buildBackendUrl", () => {
  it("prepends the base URL", () => {
    const url = buildBackendUrl("/api/estimates");
    expect(url).toContain("/api/estimates");
    expect(url.startsWith("http")).toBe(true);
  });
});

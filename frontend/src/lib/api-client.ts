/**
 * Centralized API client for all backend HTTP requests.
 *
 * Usage:
 *   import { apiClient } from "@/lib/api-client";
 *   const data = await apiClient.get<EstimateListResponse>("/api/estimates", token);
 *
 * All methods throw `ApiError` on non-2xx responses with a typed error message
 * extracted from the backend's standard error envelope:
 *   { error: { message, code, details } }  or  { detail: string | [...] }
 */

import { ApiError } from "@/types/api";

const BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(
  /\/$/,
  ""
);

// ---------------------------------------------------------------------------
// Error extraction — handles FastAPI's various error shapes
// ---------------------------------------------------------------------------

async function extractErrorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (body?.error?.message) return body.error.message;
    if (typeof body?.detail === "string") return body.detail;
    if (body?.detail?.message) return body.detail.message;
    if (Array.isArray(body?.detail) && body.detail.length > 0) {
      const first = body.detail[0];
      return first?.msg ?? first?.message ?? JSON.stringify(first);
    }
  } catch {
    // Response body not JSON — fall through to default
  }
  return `HTTP ${res.status}: ${res.statusText}`;
}

// ---------------------------------------------------------------------------
// Core request helper
// ---------------------------------------------------------------------------

async function request<T>(
  method: string,
  path: string,
  options: {
    token?: string;
    body?: unknown;
    signal?: AbortSignal;
    isFormData?: boolean;
  } = {}
): Promise<T> {
  const { token, body, signal, isFormData } = options;

  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (body !== undefined && !isFormData) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: isFormData ? (body as FormData) : body !== undefined ? JSON.stringify(body) : undefined,
    signal,
    cache: "no-store",
  });

  // Surface the backend correlation ID in dev to aid debugging
  if (process.env.NODE_ENV === "development") {
    const requestId = res.headers.get("x-request-id");
    if (requestId) console.debug("[api] X-Request-ID:", requestId);
  }

  if (!res.ok) {
    const message = await extractErrorMessage(res);
    throw new ApiError(message, res.status);
  }

  // Handle 204 No Content
  if (res.status === 204) return undefined as T;

  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Public API client
// ---------------------------------------------------------------------------

export const apiClient = {
  get<T>(path: string, token?: string, signal?: AbortSignal): Promise<T> {
    return request<T>("GET", path, { token, signal });
  },

  post<T>(path: string, body?: unknown, token?: string, signal?: AbortSignal): Promise<T> {
    return request<T>("POST", path, { body, token, signal });
  },

  patch<T>(path: string, body?: unknown, token?: string, signal?: AbortSignal): Promise<T> {
    return request<T>("PATCH", path, { body, token, signal });
  },

  delete<T>(path: string, token?: string, signal?: AbortSignal): Promise<T> {
    return request<T>("DELETE", path, { token, signal });
  },

  postForm<T>(path: string, formData: FormData, token?: string, signal?: AbortSignal): Promise<T> {
    return request<T>("POST", path, {
      body: formData,
      token,
      signal,
      isFormData: true,
    });
  },
};

/**
 * Build a full backend URL (for SSE EventSource which doesn't use apiClient).
 */
export function buildBackendUrl(path: string): string {
  return `${BASE_URL}${path}`;
}

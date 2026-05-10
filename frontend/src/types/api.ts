/**
 * Generic API types shared across all services.
 */

/** A structured API error with an optional error code and details. */
export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
    public readonly details?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Generic paginated response wrapper. */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

/** Generic success envelope. */
export interface ApiSuccessResponse<T = void> {
  data: T;
  message?: string;
}

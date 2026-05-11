/**
 * Type definitions for the Auth domain.
 * Mirrors the Pydantic schemas in backend/app/api/schemas/auth_schemas.py.
 */

export type UserRole = "homeowner" | "qs_engineer" | "contractor";

export interface RegisterRequest {
  name: string;
  email: string;
  password: string;
  role?: UserRole;
}

export interface RegisterResponse {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  created_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  access_token: string;
}

export interface ForgotPasswordRequest {
  email: string;
}

export interface ForgotPasswordResponse {
  message: string;
  /** Only present in development environments for testing. */
  dev_reset_token?: string;
}

export interface ResetPasswordRequest {
  token: string;
  new_password: string;
}

export interface ResetPasswordResponse {
  message: string;
}

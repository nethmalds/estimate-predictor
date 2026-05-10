/**
 * Auth service — wraps registration, forgot-password, and reset-password
 * endpoints.
 *
 * Note: The login flow is handled by NextAuth's `authorize` callback in
 * src/auth.ts and cannot be replaced with this client-side service.
 */

import { apiClient } from "@/lib/api-client";
import type {
  ForgotPasswordRequest,
  ForgotPasswordResponse,
  RegisterRequest,
  RegisterResponse,
  ResetPasswordRequest,
  ResetPasswordResponse,
} from "@/types/auth";

/**
 * Register a new user account.
 */
export async function register(
  payload: RegisterRequest
): Promise<RegisterResponse> {
  return apiClient.post<RegisterResponse>("/api/users/register", payload);
}

/**
 * Request a password-reset email.
 * Always returns 200 (backend prevents user enumeration).
 */
export async function forgotPassword(
  payload: ForgotPasswordRequest
): Promise<ForgotPasswordResponse> {
  return apiClient.post<ForgotPasswordResponse>(
    "/api/auth/forgot-password",
    payload
  );
}

/**
 * Submit a password reset using the token from the reset email.
 */
export async function resetPassword(
  payload: ResetPasswordRequest
): Promise<ResetPasswordResponse> {
  return apiClient.post<ResetPasswordResponse>(
    "/api/auth/reset-password",
    payload
  );
}

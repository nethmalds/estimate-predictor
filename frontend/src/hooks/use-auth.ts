/**
 * Auth hooks — useMutation wrappers for register, forgot-password,
 * and reset-password flows.
 *
 * Usage:
 *   const { mutate: doRegister, isPending } = useRegister();
 *   doRegister(payload, { onSuccess, onError });
 */

"use client";

import { useMutation } from "@tanstack/react-query";
import {
  register,
  forgotPassword,
  resetPassword,
} from "@/services/auth.service";
import type {
  ForgotPasswordRequest,
  RegisterRequest,
  ResetPasswordRequest,
} from "@/types/auth";

/**
 * Register a new user account.
 */
export function useRegister() {
  return useMutation({
    mutationFn: (payload: RegisterRequest) => register(payload),
  });
}

/**
 * Request a password-reset email.
 */
export function useForgotPassword() {
  return useMutation({
    mutationFn: (payload: ForgotPasswordRequest) => forgotPassword(payload),
  });
}

/**
 * Submit a password reset using the token from the email.
 */
export function useResetPassword() {
  return useMutation({
    mutationFn: (payload: ResetPasswordRequest) => resetPassword(payload),
  });
}

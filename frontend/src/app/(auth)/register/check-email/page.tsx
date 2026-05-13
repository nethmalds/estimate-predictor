// NEW: H11 — Post-registration "check your inbox" confirmation page.
"use client";

import { useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Building2, Mail, Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { resendVerification } from "@/services/auth.service";
import { ApiError } from "@/types/api";
import { Button } from "@/components/ui/button";

function CheckEmailContent() {
  const searchParams = useSearchParams();
  const email = searchParams.get("email") ?? "";

  const [resendState, setResendState] = useState<"idle" | "loading" | "sent" | "error">("idle");
  const [resendError, setResendError] = useState<string | null>(null);

  const handleResend = async () => {
    if (!email || resendState === "loading") return;
    setResendState("loading");
    setResendError(null);
    try {
      await resendVerification({ email });
      setResendState("sent");
    } catch (err) {
      setResendError(
        err instanceof ApiError ? err.message : "Could not resend email. Please try again later."
      );
      setResendState("error");
    }
  };

  return (
    <div className="w-full max-w-md">
      {/* Header */}
      <div className="mb-8 text-center">
        <div className="mb-5 inline-flex h-14 w-14 items-center justify-center rounded-2xl border border-blue-500/20 bg-blue-500/10 shadow-lg shadow-blue-500/10">
          <Building2 className="h-7 w-7 text-blue-400" />
        </div>
        <h1 className="text-3xl font-bold tracking-tight text-zinc-100">Check your inbox</h1>
        <p className="mt-2 text-sm text-zinc-400">
          We sent a verification link to your email address
        </p>
      </div>

      {/* Card */}
      <div className="rounded-2xl border border-zinc-800/80 bg-zinc-900/80 p-8 text-center shadow-2xl shadow-black/40 backdrop-blur-sm">
        {/* Icon */}
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full border border-blue-500/20 bg-blue-500/10">
          <Mail className="h-8 w-8 text-blue-400" />
        </div>

        {email && <p className="mb-2 text-sm text-zinc-300">We sent a verification email to</p>}
        {email && <p className="mb-6 font-semibold break-all text-zinc-100">{email}</p>}

        <p className="mb-8 text-sm text-zinc-400">
          Click the link in that email to activate your account. The link is valid for{" "}
          <span className="text-zinc-300">24 hours</span>.
        </p>

        {/* Resend section */}
        {resendState === "sent" ? (
          <div className="mb-6 flex items-center justify-center gap-2 text-sm text-green-400">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            <span>Verification email resent successfully.</span>
          </div>
        ) : (
          <>
            {resendError && (
              <div
                role="alert"
                aria-live="polite"
                className="mb-4 flex items-start gap-3 rounded-xl border border-red-500/25 bg-red-500/10 px-4 py-3.5 text-sm text-red-400"
              >
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                <span>{resendError}</span>
              </div>
            )}
            <p className="mb-3 text-sm text-zinc-500">
              Didn&apos;t receive it? Check your spam folder or
            </p>
            <Button
              variant="outline"
              onClick={handleResend}
              disabled={resendState === "loading" || !email}
              className="w-full rounded-xl border-zinc-700 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100"
            >
              {resendState === "loading" ? (
                <span className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Resending...
                </span>
              ) : (
                "Resend verification email"
              )}
            </Button>
          </>
        )}

        {/* Divider */}
        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-zinc-800" />
          </div>
        </div>

        <p className="text-center text-sm text-zinc-500">
          Already verified?{" "}
          <Link
            href="/login"
            className="font-medium text-blue-400 transition-colors hover:text-blue-300"
          >
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function CheckEmailPage() {
  return (
    <Suspense>
      <CheckEmailContent />
    </Suspense>
  );
}

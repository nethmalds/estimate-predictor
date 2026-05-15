"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Building2,
  Loader2,
  Mail,
  Lock,
  ArrowRight,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import { resendVerification } from "@/services/auth.service";
import { ApiError } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  // NEW: H11 — track whether login was rejected due to unverified email
  const [emailNotVerified, setEmailNotVerified] = useState(false);
  const [resendState, setResendState] = useState<"idle" | "loading" | "sent">("idle");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setEmailNotVerified(false);
    setResendState("idle");
    setLoading(true);
    const result = await signIn("credentials", {
      email,
      password,
      redirect: false,
    });
    setLoading(false);
    if (!result?.error) {
      router.push("/dashboard");
      return;
    }
    // NEW: H11 — detect the email_not_verified code surfaced from auth.ts
    if (result.code === "email_not_verified") {
      setEmailNotVerified(true);
      setError("Your email address has not been verified yet.");
    } else {
      setError("Invalid email or password. Please try again.");
    }
  };

  // NEW: H11 — resend handler used from the error state below the form
  const handleResend = async () => {
    if (resendState === "loading" || !email) return;
    setResendState("loading");
    try {
      await resendVerification({ email });
      setResendState("sent");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not resend email. Try again later.");
      setResendState("idle");
    }
  };

  return (
    <div className="w-full max-w-md">
      {/* Header */}
      <div className="mb-8 text-center">
        <div className="mb-5 inline-flex h-14 w-14 items-center justify-center rounded-2xl border border-blue-500/20 bg-blue-500/10 shadow-lg shadow-blue-500/10">
          <Building2 className="h-7 w-7 text-blue-400" />
        </div>
        <h1 className="text-3xl font-bold tracking-tight text-zinc-900">Welcome back</h1>
        <p className="mt-2 text-sm text-zinc-500">Sign in to access your estimates dashboard</p>
      </div>

      {/* Card */}
      <div className="rounded-2xl border border-zinc-200/80 bg-white/80 p-8 shadow-2xl shadow-zinc-200/40 backdrop-blur-sm">
        {/* Error alert */}
        {error && (
          <div
            role="alert"
            aria-live="polite"
            className="mb-4 flex items-start gap-3 rounded-xl border border-red-500/25 bg-red-500/10 px-4 py-3.5 text-sm text-red-400"
          >
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{error}</span>
          </div>
        )}

        {/* NEW: H11 — resend verification prompt shown when email is not verified */}
        {emailNotVerified && (
          <div className="mb-6">
            {resendState === "sent" ? (
              <div className="flex items-center gap-2 rounded-xl border border-green-500/25 bg-green-500/10 px-4 py-3 text-sm text-green-400">
                <CheckCircle2 className="h-4 w-4 shrink-0" />
                <span>Verification email resent — check your inbox.</span>
              </div>
            ) : (
              <Button
                type="button"
                variant="outline"
                onClick={handleResend}
                disabled={resendState === "loading"}
                className="w-full rounded-xl border-zinc-300 text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900"
              >
                {resendState === "loading" ? (
                  <span className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Resending…
                  </span>
                ) : (
                  "Resend verification email"
                )}
              </Button>
            )}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Email */}
          <div className="space-y-2">
            <Label htmlFor="email" className="text-sm font-medium text-zinc-700">
              Email address
            </Label>
            <div className="relative">
              <Mail className="absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-zinc-400" />
              <Input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="h-11 rounded-xl border-zinc-300/60 bg-zinc-50/60 pl-9 text-zinc-900 placeholder:text-zinc-400 focus-visible:border-blue-500/70 focus-visible:ring-blue-500/20"
              />
            </div>
          </div>

          {/* Password */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="password" className="text-sm font-medium text-zinc-700">
                Password
              </Label>
              <Link
                href="/forgot-password"
                className="text-xs text-blue-400 transition-colors hover:text-blue-300"
              >
                Forgot password?
              </Link>
            </div>
            <div className="relative">
              <Lock className="absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-zinc-400" />
              <Input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="h-11 rounded-xl border-zinc-300/60 bg-zinc-50/60 pl-9 text-zinc-900 placeholder:text-zinc-400 focus-visible:border-blue-500/70 focus-visible:ring-blue-500/20"
              />
            </div>
          </div>

          {/* Submit */}
          <Button
            type="submit"
            disabled={loading}
            className="mt-2 h-11 w-full rounded-xl bg-blue-600 font-semibold text-white shadow-lg shadow-blue-600/25 transition-all duration-200 hover:-translate-y-0.5 hover:bg-blue-500 hover:shadow-blue-500/30 disabled:translate-y-0 disabled:opacity-60"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Signing in...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                Sign in
                <ArrowRight className="h-4 w-4" />
              </span>
            )}
          </Button>
        </form>

        {/* Divider */}
        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-zinc-200" />
          </div>
          <div className="relative flex justify-center text-xs">
            <span className="bg-white px-3 text-zinc-500">New here?</span>
          </div>
        </div>

        <p className="text-center text-sm text-zinc-500">
          Don&apos;t have an account?{" "}
          <Link
            href="/register"
            className="font-medium text-blue-400 transition-colors hover:text-blue-300"
          >
            Create one free
          </Link>
        </p>
      </div>

      {/* Footer note */}
      <p className="mt-6 text-center text-xs text-zinc-600">
        By signing in, you agree to our{" "}
        <button
          type="button"
          className="text-zinc-500 underline-offset-2 transition-colors hover:text-zinc-400 hover:underline"
        >
          Terms of Service
        </button>{" "}
        and{" "}
        <button
          type="button"
          className="text-zinc-500 underline-offset-2 transition-colors hover:text-zinc-400 hover:underline"
        >
          Privacy Policy
        </button>
        .
      </p>
    </div>
  );
}

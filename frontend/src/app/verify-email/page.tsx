// NEW: H11 — Email verification landing page.
// Reads ?token= from the URL, calls the backend, and redirects to login on success.
"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Building2, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { verifyEmail } from "@/services/auth.service";
import { ApiError } from "@/types/api";
import { Button } from "@/components/ui/button";

type VerifyState = "loading" | "success" | "error";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("token") ?? "";

  const [state, setState] = useState<VerifyState>("loading");
  const [message, setMessage] = useState<string>("");

  useEffect(() => {
    if (!token) {
      setState("error");
      setMessage("No verification token found in the link. Please check your email and try again.");
      return;
    }

    let cancelled = false;
    verifyEmail(token)
      .then((res) => {
        if (cancelled) return;
        setState("success");
        setMessage(res.message);
        // NEW: Auto-redirect to login after 3 seconds on success
        setTimeout(() => {
          if (!cancelled) router.push("/login");
        }, 3000);
      })
      .catch((err) => {
        if (cancelled) return;
        setState("error");
        setMessage(
          err instanceof ApiError ? err.message : "Verification failed. Please request a new link."
        );
      });

    return () => {
      cancelled = true;
    };
  }, [token, router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-950 px-4">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="mb-8 text-center">
          <div className="mb-5 inline-flex h-14 w-14 items-center justify-center rounded-2xl border border-blue-500/20 bg-blue-500/10 shadow-lg shadow-blue-500/10">
            <Building2 className="h-7 w-7 text-blue-400" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-zinc-100">
            {state === "loading"
              ? "Verifying your email…"
              : state === "success"
                ? "Email verified!"
                : "Verification failed"}
          </h1>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-zinc-800/80 bg-zinc-900/80 p-8 text-center shadow-2xl shadow-black/40 backdrop-blur-sm">
          {state === "loading" && (
            <div className="flex flex-col items-center gap-4">
              <Loader2 className="h-10 w-10 animate-spin text-blue-400" />
              <p className="text-sm text-zinc-400">Please wait…</p>
            </div>
          )}

          {state === "success" && (
            <div className="flex flex-col items-center gap-4">
              <CheckCircle2 className="h-12 w-12 text-green-400" />
              <p className="text-sm text-zinc-300">{message}</p>
              <p className="text-xs text-zinc-500">Redirecting you to the login page…</p>
              <Button
                onClick={() => router.push("/login")}
                className="mt-2 rounded-xl bg-blue-600 font-semibold text-white hover:bg-blue-500"
              >
                Go to login
              </Button>
            </div>
          )}

          {state === "error" && (
            <div className="flex flex-col items-center gap-4">
              <XCircle className="h-12 w-12 text-red-400" />
              <p className="text-sm text-zinc-300">{message}</p>
              <p className="mt-2 text-sm text-zinc-500">
                You can request a new link from the login page.
              </p>
              <Link href="/login">
                <Button
                  variant="outline"
                  className="mt-2 rounded-xl border-zinc-700 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100"
                >
                  Back to login
                </Button>
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense>
      <VerifyEmailContent />
    </Suspense>
  );
}

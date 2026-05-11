"use client";

import { useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Building2, Loader2 } from "lucide-react";
import { resetPassword } from "@/services/auth.service";
import { ApiError } from "@/types/api";

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirm) { setError("Passwords do not match."); return; }
    setError(null);
    setLoading(true);
    try {
      await resetPassword({ token, new_password: password });
      setDone(true);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Reset failed. The link may have expired."
      );
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 text-center text-zinc-400 text-sm">
        Invalid or missing reset token.{" "}
        <Link href="/forgot-password" className="text-blue-400 hover:text-blue-300">Request a new link</Link>
      </div>
    );
  }

  if (done) {
    return (
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 text-center">
        <p className="text-zinc-300 text-sm mb-4">Password reset successfully. You can now sign in.</p>
        <Link href="/login" className="text-blue-400 hover:text-blue-300 text-sm">Sign in</Link>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-4">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-sm rounded-lg px-4 py-3">{error}</div>
      )}
      <div>
        <label className="block text-sm font-medium text-zinc-300 mb-1.5">New password</label>
        <input
          type="password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Min. 8 characters"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-zinc-300 mb-1.5">Confirm new password</label>
        <input
          type="password"
          required
          minLength={8}
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Re-enter new password"
        />
      </div>
      <button
        type="submit"
        disabled={loading}
        className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white rounded-lg font-semibold text-sm transition-colors"
      >
        {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> Resetting...</> : "Reset password"}
      </button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <Building2 className="w-8 h-8 text-blue-400 mx-auto mb-3" />
          <h1 className="text-2xl font-bold">Set new password</h1>
          <p className="text-zinc-400 text-sm mt-1">Choose a strong password for your account.</p>
        </div>
        <Suspense fallback={<div className="text-zinc-500 text-sm text-center">Loading...</div>}>
          <ResetPasswordForm />
        </Suspense>
        <p className="text-center text-sm text-zinc-500 mt-4">
          <Link href="/login" className="text-blue-400 hover:text-blue-300">Back to sign in</Link>
        </p>
      </div>
    </div>
  );
}

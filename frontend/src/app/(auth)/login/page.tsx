"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Building2, Loader2, Mail, Lock, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const result = await signIn("credentials", {
      email,
      password,
      redirect: false,
    });
    setLoading(false);
    if (result?.error) {
      setError("Invalid email or password. Please try again.");
    } else {
      router.push("/dashboard");
    }
  };

  return (
    <div className="w-full max-w-md">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-blue-500/10 border border-blue-500/20 mb-5 shadow-lg shadow-blue-500/10">
          <Building2 className="w-7 h-7 text-blue-400" />
        </div>
        <h1 className="text-3xl font-bold text-zinc-100 tracking-tight">Welcome back</h1>
        <p className="text-zinc-400 text-sm mt-2">
          Sign in to access your estimates dashboard
        </p>
      </div>

      {/* Card */}
      <div className="bg-zinc-900/80 border border-zinc-800/80 rounded-2xl p-8 shadow-2xl shadow-black/40 backdrop-blur-sm">
        {/* Error alert */}
        {error && (
          <div className="mb-6 flex items-start gap-3 bg-red-500/10 border border-red-500/25 text-red-400 text-sm rounded-xl px-4 py-3.5">
            <span className="shrink-0 mt-0.5">⚠</span>
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Email */}
          <div className="space-y-2">
            <Label htmlFor="email" className="text-zinc-300 text-sm font-medium">
              Email address
            </Label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
              <Input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="pl-9 h-11 bg-zinc-800/60 border-zinc-700/60 text-zinc-100 placeholder:text-zinc-500 focus-visible:border-blue-500/70 focus-visible:ring-blue-500/20 rounded-xl"
              />
            </div>
          </div>

          {/* Password */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="password" className="text-zinc-300 text-sm font-medium">
                Password
              </Label>
              <Link
                href="/forgot-password"
                className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
              >
                Forgot password?
              </Link>
            </div>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
              <Input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="pl-9 h-11 bg-zinc-800/60 border-zinc-700/60 text-zinc-100 placeholder:text-zinc-500 focus-visible:border-blue-500/70 focus-visible:ring-blue-500/20 rounded-xl"
              />
            </div>
          </div>

          {/* Submit */}
          <Button
            type="submit"
            disabled={loading}
            className="w-full h-11 mt-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl shadow-lg shadow-blue-600/25 transition-all duration-200 hover:shadow-blue-500/30 hover:-translate-y-0.5 disabled:opacity-60 disabled:translate-y-0"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                Signing in...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                Sign in
                <ArrowRight className="w-4 h-4" />
              </span>
            )}
          </Button>
        </form>

        {/* Divider */}
        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-zinc-800" />
          </div>
          <div className="relative flex justify-center text-xs">
            <span className="bg-zinc-900 px-3 text-zinc-600">New here?</span>
          </div>
        </div>

        <p className="text-center text-sm text-zinc-500">
          Don&apos;t have an account?{" "}
          <Link
            href="/register"
            className="text-blue-400 hover:text-blue-300 font-medium transition-colors"
          >
            Create one free
          </Link>
        </p>
      </div>

      {/* Footer note */}
      <p className="text-center text-xs text-zinc-600 mt-6">
        By signing in, you agree to our{" "}
        <span className="text-zinc-500 hover:text-zinc-400 cursor-pointer transition-colors">
          Terms of Service
        </span>{" "}
        and{" "}
        <span className="text-zinc-500 hover:text-zinc-400 cursor-pointer transition-colors">
          Privacy Policy
        </span>
        .
      </p>
    </div>
  );
}

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Building2,
  Loader2,
  User,
  Mail,
  Lock,
  ShieldCheck,
  ArrowRight,
  AlertCircle,
} from "lucide-react";
import { register } from "@/services/auth.service";
import { ApiError } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const ROLES = [
  { value: "homeowner", label: "Homeowner" },
  { value: "contractor", label: "Contractor" },
  { value: "qs_engineer", label: "Quantity Surveyor" },
];

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    confirmPassword: "",
    role: "homeowner",
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (form.password !== form.confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      await register({
        name: form.name,
        email: form.email,
        password: form.password,
        role: form.role as "homeowner" | "qs_engineer" | "contractor",
      });
      // NEW: H11 — redirect to "check your inbox" page instead of straight to login
      router.push(`/register/check-email?email=${encodeURIComponent(form.email)}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Registration failed. Please try again.");
      setLoading(false);
    }
  };

  const setField = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  const inputClass =
    "h-11 bg-zinc-800/60 border-zinc-700/60 text-zinc-100 placeholder:text-zinc-500 focus-visible:border-blue-500/70 focus-visible:ring-blue-500/20 rounded-xl";

  return (
    <div className="w-full max-w-md">
      {/* Header */}
      <div className="mb-8 text-center">
        <div className="mb-5 inline-flex h-14 w-14 items-center justify-center rounded-2xl border border-blue-500/20 bg-blue-500/10 shadow-lg shadow-blue-500/10">
          <Building2 className="h-7 w-7 text-blue-400" />
        </div>
        <h1 className="text-3xl font-bold tracking-tight text-zinc-100">Create account</h1>
        <p className="mt-2 text-sm text-zinc-400">Start generating AI-powered estimates for free</p>
      </div>

      {/* Card */}
      <div className="rounded-2xl border border-zinc-800/80 bg-zinc-900/80 p-8 shadow-2xl shadow-black/40 backdrop-blur-sm">
        {/* Error */}
        {error && (
          <div
            role="alert"
            aria-live="polite"
            className="mb-6 flex items-start gap-3 rounded-xl border border-red-500/25 bg-red-500/10 px-4 py-3.5 text-sm text-red-400"
          >
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Full name */}
          <div className="space-y-2">
            <Label htmlFor="name" className="text-sm font-medium text-zinc-300">
              Full name
            </Label>
            <div className="relative">
              <User className="absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-zinc-500" />
              <Input
                id="name"
                type="text"
                required
                value={form.name}
                onChange={setField("name")}
                placeholder="Jane Smith"
                className={`pl-9 ${inputClass}`}
              />
            </div>
          </div>

          {/* Email */}
          <div className="space-y-2">
            <Label htmlFor="email" className="text-sm font-medium text-zinc-300">
              Email address
            </Label>
            <div className="relative">
              <Mail className="absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-zinc-500" />
              <Input
                id="email"
                type="email"
                required
                value={form.email}
                onChange={setField("email")}
                placeholder="you@example.com"
                className={`pl-9 ${inputClass}`}
              />
            </div>
          </div>

          {/* Password row */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="password" className="text-sm font-medium text-zinc-300">
                Password
              </Label>
              <div className="relative">
                <Lock className="absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-zinc-500" />
                <Input
                  id="password"
                  type="password"
                  required
                  minLength={8}
                  value={form.password}
                  onChange={setField("password")}
                  placeholder="Min. 8 chars"
                  className={`pl-9 ${inputClass}`}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmPassword" className="text-sm font-medium text-zinc-300">
                Confirm
              </Label>
              <div className="relative">
                <ShieldCheck className="absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-zinc-500" />
                <Input
                  id="confirmPassword"
                  type="password"
                  required
                  minLength={8}
                  value={form.confirmPassword}
                  onChange={setField("confirmPassword")}
                  placeholder="Re-enter"
                  className={`pl-9 ${inputClass}`}
                />
              </div>
            </div>
          </div>

          {/* Role */}
          <div className="space-y-2">
            <Label htmlFor="role" className="text-sm font-medium text-zinc-300">
              I am a&hellip;
            </Label>
            <Select
              value={form.role}
              onValueChange={(val) => setForm((f) => ({ ...f, role: val }))}
            >
              <SelectTrigger
                id="role"
                className="h-11 w-full rounded-xl border-zinc-700/60 bg-zinc-800/60 text-zinc-100 focus:border-blue-500/70 focus:ring-blue-500/20"
              >
                <SelectValue placeholder="Select your role" />
              </SelectTrigger>
              <SelectContent className="border-zinc-800 bg-zinc-900 text-zinc-100">
                {ROLES.map((r) => (
                  <SelectItem
                    key={r.value}
                    value={r.value}
                    className="focus:bg-zinc-800 focus:text-zinc-100"
                  >
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
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
                Creating account...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                Create account
                <ArrowRight className="h-4 w-4" />
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
            <span className="bg-zinc-900 px-3 text-zinc-600">Already registered?</span>
          </div>
        </div>

        <p className="text-center text-sm text-zinc-500">
          Have an account?{" "}
          <Link
            href="/login"
            className="font-medium text-blue-400 transition-colors hover:text-blue-300"
          >
            Sign in instead
          </Link>
        </p>
      </div>

      {/* Footer note */}
      <p className="mt-6 text-center text-xs text-zinc-600">
        By registering, you agree to our{" "}
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

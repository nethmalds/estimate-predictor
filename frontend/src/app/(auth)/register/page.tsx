"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Building2, Loader2, User, Mail, Lock, ShieldCheck, ArrowRight } from "lucide-react";
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
  { value: "quantity_surveyor", label: "Quantity Surveyor" },
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
      router.push("/login?registered=1");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Registration failed. Please try again.");
      setLoading(false);
    }
  };

  const setField =
    (field: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm((f) => ({ ...f, [field]: e.target.value }));

  const inputClass =
    "h-11 bg-zinc-800/60 border-zinc-700/60 text-zinc-100 placeholder:text-zinc-500 focus-visible:border-blue-500/70 focus-visible:ring-blue-500/20 rounded-xl";

  return (
    <div className="w-full max-w-md">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-blue-500/10 border border-blue-500/20 mb-5 shadow-lg shadow-blue-500/10">
          <Building2 className="w-7 h-7 text-blue-400" />
        </div>
        <h1 className="text-3xl font-bold text-zinc-100 tracking-tight">Create account</h1>
        <p className="text-zinc-400 text-sm mt-2">
          Start generating AI-powered estimates for free
        </p>
      </div>

      {/* Card */}
      <div className="bg-zinc-900/80 border border-zinc-800/80 rounded-2xl p-8 shadow-2xl shadow-black/40 backdrop-blur-sm">
        {/* Error */}
        {error && (
          <div className="mb-6 flex items-start gap-3 bg-red-500/10 border border-red-500/25 text-red-400 text-sm rounded-xl px-4 py-3.5">
            <span className="shrink-0 mt-0.5">⚠</span>
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Full name */}
          <div className="space-y-2">
            <Label htmlFor="name" className="text-zinc-300 text-sm font-medium">
              Full name
            </Label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
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
            <Label htmlFor="email" className="text-zinc-300 text-sm font-medium">
              Email address
            </Label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
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
              <Label htmlFor="password" className="text-zinc-300 text-sm font-medium">
                Password
              </Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
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
              <Label htmlFor="confirmPassword" className="text-zinc-300 text-sm font-medium">
                Confirm
              </Label>
              <div className="relative">
                <ShieldCheck className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
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
            <Label htmlFor="role" className="text-zinc-300 text-sm font-medium">
              I am a&hellip;
            </Label>
            <Select
              value={form.role}
              onValueChange={(val) => setForm((f) => ({ ...f, role: val }))}
            >
              <SelectTrigger
                id="role"
                className="h-11 w-full bg-zinc-800/60 border-zinc-700/60 text-zinc-100 rounded-xl focus:border-blue-500/70 focus:ring-blue-500/20"
              >
                <SelectValue placeholder="Select your role" />
              </SelectTrigger>
              <SelectContent className="bg-zinc-900 border-zinc-800 text-zinc-100">
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
            className="w-full h-11 mt-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl shadow-lg shadow-blue-600/25 transition-all duration-200 hover:shadow-blue-500/30 hover:-translate-y-0.5 disabled:opacity-60 disabled:translate-y-0"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                Creating account...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                Create account
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
            <span className="bg-zinc-900 px-3 text-zinc-600">Already registered?</span>
          </div>
        </div>

        <p className="text-center text-sm text-zinc-500">
          Have an account?{" "}
          <Link
            href="/login"
            className="text-blue-400 hover:text-blue-300 font-medium transition-colors"
          >
            Sign in instead
          </Link>
        </p>
      </div>

      {/* Footer note */}
      <p className="text-center text-xs text-zinc-600 mt-6">
        By registering, you agree to our{" "}
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

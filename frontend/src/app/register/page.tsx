"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Building2, Loader2 } from "lucide-react";
import { register } from "@/services/auth.service";
import { ApiError } from "@/types/api";

const ROLES = [
  { value: "homeowner", label: "Homeowner" },
  { value: "contractor", label: "Contractor" },
  { value: "quantity_surveyor", label: "Quantity Surveyor" },
];

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({ name: "", email: "", password: "", confirmPassword: "", role: "homeowner" });
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
      await register({ name: form.name, email: form.email, password: form.password, role: form.role as "homeowner" | "qs_engineer" | "contractor" });
      router.push("/login?registered=1");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Registration failed.");
      setLoading(false);
    }
  };

  const set = (field: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <Building2 className="w-8 h-8 text-blue-400 mx-auto mb-3" />
          <h1 className="text-2xl font-bold">Create account</h1>
          <p className="text-zinc-400 text-sm mt-1">Start generating estimates for free</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-4">
          {error && (
            <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-sm rounded-lg px-4 py-3">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-1.5">Full name</label>
            <input
              type="text"
              required
              value={form.name}
              onChange={set("name")}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Jane Smith"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-1.5">Email</label>
            <input
              type="email"
              required
              value={form.email}
              onChange={set("email")}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-1.5">Password</label>
            <input
              type="password"
              required
              minLength={8}
              value={form.password}
              onChange={set("password")}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Min. 8 characters"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-1.5">Confirm password</label>
            <input
              type="password"
              required
              minLength={8}
              value={form.confirmPassword}
              onChange={set("confirmPassword")}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Re-enter password"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-1.5">Role</label>
            <select
              value={form.role}
              onChange={set("role")}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2.5 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {ROLES.map((r) => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white rounded-lg font-semibold text-sm transition-colors"
          >
            {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> Creating account...</> : "Create account"}
          </button>
        </form>

        <p className="text-center text-sm text-zinc-500 mt-4">
          Already have an account?{" "}
          <Link href="/login" className="text-blue-400 hover:text-blue-300">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}

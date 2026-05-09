import { auth } from "@/auth";
import { redirect } from "next/navigation";
import Link from "next/link";
import { Building2, Plus, FileText, TrendingUp, DollarSign } from "lucide-react";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

interface DashboardSummary {
  total_estimates: number;
  estimates_this_month: number;
  average_confidence: number;
  total_estimated_value: number;
}

interface EstimateItem {
  id: string;
  project_name: string | null;
  status: string;
  grand_total: number | null;
  confidence: number | null;
  created_at: string;
}

async function fetchSummary(accessToken: string): Promise<DashboardSummary | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/dashboard/summary`, {
      cache: "no-store",
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function fetchEstimates(accessToken: string): Promise<EstimateItem[]> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/estimates?page_size=10`, {
      cache: "no-store",
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data.estimates ?? [];
  } catch {
    return [];
  }
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    completed: "bg-green-500/10 text-green-400 border-green-500/20",
    in_progress: "bg-blue-500/10 text-blue-400 border-blue-500/20",
    failed: "bg-red-500/10 text-red-400 border-red-500/20",
  };
  return (
    <span className={`text-xs border rounded-full px-2 py-0.5 font-medium ${map[status] ?? "bg-zinc-700 text-zinc-300"}`}>
      {status.replace("_", " ")}
    </span>
  );
}

export default async function DashboardPage() {
  const session = await auth();
  if (!session?.user?.id) redirect("/login");
  const accessToken = (session.user as { accessToken?: string }).accessToken ?? "";

  const [summary, estimates] = await Promise.all([
    fetchSummary(accessToken),
    fetchEstimates(accessToken),
  ]);

  const stats = [
    { label: "Total Estimates", value: summary?.total_estimates ?? 0, icon: <FileText className="w-5 h-5 text-blue-400" /> },
    { label: "This Month", value: summary?.estimates_this_month ?? 0, icon: <TrendingUp className="w-5 h-5 text-green-400" /> },
    { label: "Avg Confidence", value: summary ? `${((summary.average_confidence ?? 0) * 100).toFixed(1)}%` : "—", icon: <TrendingUp className="w-5 h-5 text-yellow-400" /> },
    { label: "Total Value (LKR)", value: summary ? `${(summary.total_estimated_value / 1_000_000).toFixed(1)}M` : "—", icon: <DollarSign className="w-5 h-5 text-purple-400" /> },
  ];

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* ── Header ── */}
      <header className="border-b border-zinc-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Building2 className="w-6 h-6 text-blue-400" />
          <span className="font-bold text-lg">CostEstimate AI</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-zinc-400">{session.user.name}</span>
          <Link
            href="/estimate/new"
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
          >
            <Plus className="w-4 h-4" /> New Estimate
          </Link>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold mb-1">Dashboard</h1>
          <p className="text-zinc-400 text-sm">Welcome back, {session.user.name?.split(" ")[0]}.</p>
        </div>

        {/* ── Summary cards ── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-10">
          {stats.map((s) => (
            <div key={s.label} className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs text-zinc-400">{s.label}</p>
                {s.icon}
              </div>
              <p className="text-xl font-bold text-zinc-100">{s.value}</p>
            </div>
          ))}
        </div>

        {/* ── Recent estimates ── */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl">
          <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
            <h2 className="font-semibold">Recent Estimates</h2>
            <Link href="/estimates" className="text-sm text-blue-400 hover:text-blue-300">
              View all
            </Link>
          </div>
          {estimates.length === 0 ? (
            <div className="px-6 py-12 text-center">
              <p className="text-zinc-500 text-sm mb-4">No estimates yet.</p>
              <Link
                href="/estimate/new"
                className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium"
              >
                <Plus className="w-4 h-4" /> Create your first estimate
              </Link>
            </div>
          ) : (
            <div className="divide-y divide-zinc-800">
              {estimates.map((est) => (
                <Link
                  key={est.id}
                  href={`/estimates/${est.id}`}
                  className="flex items-center justify-between px-6 py-4 hover:bg-zinc-800/50 transition-colors"
                >
                  <div>
                    <p className="text-sm font-medium text-zinc-100">
                      {est.project_name ?? "Untitled Project"}
                    </p>
                    <p className="text-xs text-zinc-500 mt-0.5">
                      {new Date(est.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-4">
                    {est.confidence != null && (
                      <span className="text-xs text-zinc-400">
                        {(est.confidence * 100).toFixed(1)}% confidence
                      </span>
                    )}
                    {est.grand_total != null && (
                      <span className="text-sm font-medium text-zinc-100">
                        LKR {est.grand_total.toLocaleString()}
                      </span>
                    )}
                    <StatusBadge status={est.status} />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

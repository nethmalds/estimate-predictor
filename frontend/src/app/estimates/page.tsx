import { auth } from "@/auth";
import { redirect } from "next/navigation";
import Link from "next/link";
import { Building2, Plus } from "lucide-react";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

interface EstimateItem {
  id: string;
  project_name: string | null;
  status: string;
  grand_total: number | null;
  confidence: number | null;
  item_count: number | null;
  created_at: string;
}

async function fetchEstimates(accessToken: string): Promise<EstimateItem[]> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/estimates?page_size=50`, {
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

export default async function EstimatesPage() {
  const session = await auth();
  if (!session?.user?.id) redirect("/login");
  const accessToken = (session.user as { accessToken?: string }).accessToken ?? "";

  const estimates = await fetchEstimates(accessToken);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <header className="border-b border-zinc-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/dashboard" className="flex items-center gap-2">
            <Building2 className="w-6 h-6 text-blue-400" />
            <span className="font-bold text-lg">CostEstimate AI</span>
          </Link>
        </div>
        <Link
          href="/estimate/new"
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
        >
          <Plus className="w-4 h-4" /> New Estimate
        </Link>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold mb-1">All Estimates</h1>
            <p className="text-zinc-400 text-sm">{estimates.length} estimate{estimates.length !== 1 ? "s" : ""}</p>
          </div>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
          {estimates.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <p className="text-zinc-500 text-sm mb-4">No estimates yet.</p>
              <Link
                href="/estimate/new"
                className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium"
              >
                <Plus className="w-4 h-4" /> Create your first estimate
              </Link>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-5 px-6 py-3 border-b border-zinc-800 text-xs font-medium text-zinc-500 uppercase tracking-wide">
                <div className="col-span-2">Project</div>
                <div className="text-right">Items</div>
                <div className="text-right">Grand Total</div>
                <div className="text-right">Status</div>
              </div>
              <div className="divide-y divide-zinc-800">
                {estimates.map((est) => (
                  <Link
                    key={est.id}
                    href={`/estimates/${est.id}`}
                    className="grid grid-cols-5 items-center px-6 py-4 hover:bg-zinc-800/50 transition-colors"
                  >
                    <div className="col-span-2">
                      <p className="text-sm font-medium text-zinc-100">
                        {est.project_name ?? "Untitled Project"}
                      </p>
                      <p className="text-xs text-zinc-500 mt-0.5">
                        {new Date(est.created_at).toLocaleDateString()} ·{" "}
                        {est.confidence != null ? `${(est.confidence * 100).toFixed(1)}% confidence` : "—"}
                      </p>
                    </div>
                    <div className="text-right text-sm text-zinc-400">{est.item_count ?? "—"}</div>
                    <div className="text-right text-sm font-medium text-zinc-100">
                      {est.grand_total != null ? `LKR ${est.grand_total.toLocaleString()}` : "—"}
                    </div>
                    <div className="text-right">
                      <StatusBadge status={est.status} />
                    </div>
                  </Link>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

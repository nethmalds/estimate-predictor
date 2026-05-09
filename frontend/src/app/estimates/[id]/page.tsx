import { auth } from "@/auth";
import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import { Building2, ArrowLeft } from "lucide-react";
import EstimateDetailClient from "./EstimateDetailClient";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

interface Estimate {
  id: string;
  project_name: string | null;
  notes: string | null;
  status: string;
  project_info: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
  confidence: number | null;
  grand_total: number | null;
  item_count: number | null;
  created_at: string;
}

async function fetchEstimate(id: string, accessToken: string): Promise<Estimate | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/estimates/${id}`, {
      cache: "no-store",
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (res.status === 404 || res.status === 403) return null;
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export default async function EstimateDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const session = await auth();
  if (!session?.user?.id) redirect("/login");
  const accessToken = (session.user as { accessToken?: string }).accessToken ?? "";

  const estimate = await fetchEstimate(id, accessToken);
  if (!estimate) notFound();

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <header className="border-b border-zinc-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/estimates" className="flex items-center gap-2 text-zinc-400 hover:text-zinc-100">
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <Building2 className="w-6 h-6 text-blue-400" />
          <span className="font-bold text-lg">CostEstimate AI</span>
        </div>
        <Link href="/estimates" className="text-sm text-zinc-400 hover:text-zinc-100">
          All Estimates
        </Link>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8">
        <div className="mb-6">
          <h1 className="text-2xl font-bold mb-1">{estimate.project_name ?? "Untitled Project"}</h1>
          <p className="text-zinc-400 text-sm">
            Created {new Date(estimate.created_at).toLocaleDateString()} · {estimate.status.replace("_", " ")}
          </p>
        </div>

        <EstimateDetailClient estimate={estimate} userId={session.user.id} accessToken={accessToken} />
      </div>
    </div>
  );
}

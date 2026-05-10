import { auth } from "@/auth";
import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import { Building2, ArrowLeft } from "lucide-react";
import EstimateDetailClient from "./EstimateDetailClient";
import { getEstimate } from "@/services/estimates.service";

export default async function EstimateDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let session;
  try {
    session = await auth();
  } catch {
    session = null;
  }
  if (!session?.user?.id) redirect("/login");
  const accessToken = (session.user as { accessToken?: string }).accessToken ?? "";

  const estimate = await getEstimate(id, accessToken).catch(() => null);
  if (!estimate) notFound();

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="max-w-6xl mx-auto px-6 py-8">
        <Link href="/dashboard/estimates" className="inline-flex items-center gap-2 text-sm text-zinc-400 hover:text-zinc-100 mb-6 transition-colors">
          <ArrowLeft className="w-4 h-4" /> Back to Estimates
        </Link>
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

import { auth } from "@/auth";
import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import EstimateDetailClient from "./EstimateDetailClient";
import { getEstimate } from "@/services/estimates.service";
import { Button } from "@/components/ui/button";

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
    <div className="relative p-6 max-w-6xl mx-auto overflow-hidden">
      {/* Ambient glow */}
      <div className="absolute -top-24 right-1/4 w-[400px] h-[250px] bg-blue-600/10 blur-[100px] rounded-full pointer-events-none -z-10" />

      <Button variant="ghost" size="sm" asChild className="mb-6 -ml-2 text-zinc-400 hover:text-zinc-100">
        <Link href="/dashboard/estimates">
          <ArrowLeft /> Back to Estimates
        </Link>
      </Button>
      <div className="mb-6 pb-6 border-b border-border/60">
        <h1 className="text-2xl font-bold text-zinc-100">{estimate.project_name ?? "Untitled Project"}</h1>
        <p className="text-zinc-400 text-sm mt-1">
          Created {new Date(estimate.created_at).toLocaleDateString()} ·{" "}
          <span className="capitalize text-zinc-300">{estimate.status.replace("_", " ")}</span>
        </p>
      </div>

      <EstimateDetailClient estimateId={id} accessToken={accessToken} />
    </div>
  );
}


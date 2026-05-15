import type { Metadata } from "next";
import { auth } from "@/auth";
import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import EstimateDetailClient from "./EstimateDetailClient";
import { getEstimate } from "@/services/estimates.service";
import { Button } from "@/components/ui/button";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  let session;
  try {
    const { auth: getAuth } = await import("@/auth");
    session = await getAuth();
  } catch {
    session = null;
  }
  const accessToken = (session?.user as { accessToken?: string } | undefined)?.accessToken ?? "";
  const estimate = accessToken ? await getEstimate(id, accessToken).catch(() => null) : null;
  const title = estimate?.project_name ?? "Estimate Detail";
  return { title };
}

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
    <div className="relative mx-auto max-w-6xl overflow-hidden p-6">
      {/* Ambient glow */}
      <div
        className="pointer-events-none absolute -top-24 right-1/4 -z-10 h-62.5 w-100 rounded-full bg-blue-600/10 blur-[100px]"
        aria-hidden="true"
      />

      <Button
        variant="ghost"
        size="sm"
        asChild
        className="mb-6 -ml-2 text-zinc-500 hover:text-zinc-900"
      >
        <Link href="/dashboard/estimates">
          <ArrowLeft /> Back to Estimates
        </Link>
      </Button>
      <div className="border-border/60 mb-6 border-b pb-6">
        <h1 className="text-2xl font-bold text-zinc-900">
          {estimate.project_name ?? "Untitled Project"}
        </h1>
        <p className="mt-1 text-sm text-zinc-600">
          Created {new Date(estimate.created_at).toLocaleDateString()} ·{" "}
          <span className="text-zinc-700 capitalize">{estimate.status.replace("_", " ")}</span>
        </p>
      </div>

      <EstimateDetailClient estimateId={id} accessToken={accessToken} />
    </div>
  );
}

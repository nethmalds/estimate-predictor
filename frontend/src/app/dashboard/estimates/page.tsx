import type { Metadata } from "next";
import { auth } from "@/auth";
import { redirect } from "next/navigation";
import Link from "next/link";
import { Plus } from "lucide-react";
import EstimatesListClient from "./EstimatesListClient";

export const metadata: Metadata = { title: "My Estimates" };
import { Button } from "@/components/ui/button";

export default async function EstimatesPage() {
  let session;
  try {
    session = await auth();
  } catch {
    session = null;
  }
  if (!session?.user?.id) redirect("/login");
  const accessToken = (session.user as { accessToken?: string }).accessToken ?? "";

  return (
    <div className="relative mx-auto max-w-6xl space-y-6 overflow-hidden p-6">
      {/* Ambient glow */}
      <div className="pointer-events-none absolute -top-24 left-1/3 -z-10 h-[250px] w-[400px] rounded-full bg-blue-600/10 blur-[100px]" />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900">All Estimates</h1>
          <p className="mt-1 text-sm text-zinc-600">Manage your construction cost estimates</p>
        </div>
        <Button
          asChild
          className="bg-blue-600 text-white shadow-lg shadow-blue-600/20 transition-all duration-200 hover:-translate-y-0.5 hover:bg-blue-500"
        >
          <Link href="/dashboard/estimate/new">
            <Plus /> New Estimate
          </Link>
        </Button>
      </div>

      <EstimatesListClient accessToken={accessToken} />
    </div>
  );
}

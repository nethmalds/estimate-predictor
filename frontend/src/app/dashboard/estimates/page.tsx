import { auth } from "@/auth";
import { redirect } from "next/navigation";
import Link from "next/link";
import { Plus } from "lucide-react";
import EstimatesListClient from "./EstimatesListClient";
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
    <div className="relative p-6 max-w-6xl mx-auto space-y-6 overflow-hidden">
      {/* Ambient glow */}
      <div className="absolute -top-24 left-1/3 w-[400px] h-[250px] bg-blue-600/10 blur-[100px] rounded-full pointer-events-none -z-10" />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">All Estimates</h1>
          <p className="text-zinc-400 text-sm mt-1">Manage your construction cost estimates</p>
        </div>
        <Button asChild className="bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/20 hover:-translate-y-0.5 transition-all duration-200">
          <Link href="/dashboard/estimate/new">
            <Plus /> New Estimate
          </Link>
        </Button>
      </div>

      <EstimatesListClient accessToken={accessToken} />
    </div>
  );
}


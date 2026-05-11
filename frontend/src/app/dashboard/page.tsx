import { auth } from "@/auth";
import { redirect } from "next/navigation";
import Link from "next/link";
import { Plus, FileText, TrendingUp, DollarSign, Layers } from "lucide-react";
import { getDashboardSummary, listEstimates } from "@/services/estimates.service";
import type { DashboardSummary, EstimateListItem } from "@/types/estimate";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardAction } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

export default async function DashboardPage() {
  let session;
  try {
    session = await auth();
  } catch {
    session = null;
  }
  if (!session?.user?.id) redirect("/login");
  const accessToken = (session.user as { accessToken?: string }).accessToken ?? "";

  const [summary, listResponse] = await Promise.all([
    getDashboardSummary(accessToken).catch(() => null as DashboardSummary | null),
    listEstimates(accessToken, 1, 10).catch(() => null),
  ]);
  const estimates: EstimateListItem[] = listResponse?.estimates ?? [];

  const stats = [
    { label: "Total Estimates", value: summary?.total_estimates ?? 0, icon: <FileText className="w-4 h-4" />, iconColor: "text-blue-500", iconBg: "bg-blue-500/10" },
    { label: "This Month", value: summary?.estimates_this_month ?? 0, icon: <Layers className="w-4 h-4" />, iconColor: "text-emerald-500", iconBg: "bg-emerald-500/10" },
    { label: "Avg Confidence", value: summary ? `${((summary.average_confidence ?? 0) * 100).toFixed(1)}%` : "—", icon: <TrendingUp className="w-4 h-4" />, iconColor: "text-amber-500", iconBg: "bg-amber-500/10" },
    { label: "Total Value (LKR)", value: summary ? `${(summary.total_estimated_value / 1_000_000).toFixed(1)}M` : "—", icon: <DollarSign className="w-4 h-4" />, iconColor: "text-purple-500", iconBg: "bg-purple-500/10" },
  ];

  return (
    <div className="relative space-y-8 max-w-6xl mx-auto overflow-hidden">
      {/* Ambient glow — mirrors home page */}
      <div className="absolute -top-24 right-1/4 w-[500px] h-[300px] bg-blue-600/10 blur-[120px] rounded-full pointer-events-none -z-10" />

      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Dashboard</h1>
          <p className="text-zinc-400 text-sm mt-1">
            Welcome back,{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-indigo-400 font-medium">
              {session.user.name?.split(" ")[0]}
            </span>
            .
          </p>
        </div>
        <Button asChild className="bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/20 hover:-translate-y-0.5 transition-all duration-200">
          <Link href="/dashboard/estimate/new">
            <Plus /> New Estimate
          </Link>
        </Button>
      </div>

      {/* ── Summary cards ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {stats.map((s) => (
          <Card key={s.label} size="sm" className="border-border/60 bg-card/80 backdrop-blur-sm">
            <CardHeader>
              <CardTitle className="text-xs font-medium text-zinc-400">{s.label}</CardTitle>
              <CardAction>
                <div className={`p-1.5 rounded-md ${s.iconBg}`}>
                  <span className={s.iconColor}>{s.icon}</span>
                </div>
              </CardAction>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-zinc-100">{s.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* ── Recent estimates ── */}
      <Card className="border-border/60 bg-card/80 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-zinc-100">Recent Estimates</CardTitle>
          <CardAction>
            <Button variant="ghost" size="sm" asChild className="text-blue-400 hover:text-blue-300">
              <Link href="/dashboard/estimates">View all</Link>
            </Button>
          </CardAction>
        </CardHeader>
        {estimates.length === 0 ? (
          <CardContent className="py-12 text-center">
            <p className="text-zinc-400 text-sm mb-4">No estimates yet.</p>
            <Button asChild className="bg-blue-600 hover:bg-blue-500 text-white">
              <Link href="/dashboard/estimate/new">
                <Plus /> Create your first estimate
              </Link>
            </Button>
          </CardContent>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="border-border/60 hover:bg-transparent">
                <TableHead className="text-zinc-500">Project</TableHead>
                <TableHead className="hidden sm:table-cell text-zinc-500">Date</TableHead>
                <TableHead className="hidden sm:table-cell text-zinc-500">Confidence</TableHead>
                <TableHead className="text-right text-zinc-500">Total</TableHead>
                <TableHead className="text-right text-zinc-500">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {estimates.map((est) => (
                <TableRow key={est.id} className="cursor-pointer hover:bg-white/5 border-border/40">
                  <TableCell>
                    <Link href={`/dashboard/estimates/${est.id}`} className="block">
                      <p className="text-sm font-medium text-zinc-100 truncate">
                        {est.project_name ?? "Untitled Project"}
                      </p>
                      <p className="text-xs text-zinc-500 mt-0.5">
                        {est.building_type && <span className="capitalize">{est.building_type}</span>}
                        {est.built_up_area && <span className="ml-2">{est.built_up_area}</span>}
                        {est.floorplan_accepted != null && (
                          <span className={cn("ml-2", est.floorplan_accepted ? "text-green-400" : "text-zinc-600")}>
                            {est.floorplan_accepted ? "floorplan" : "no floorplan"}
                          </span>
                        )}
                      </p>
                    </Link>
                  </TableCell>
                  <TableCell className="hidden sm:table-cell text-xs text-zinc-500">
                    {new Date(est.created_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell className="hidden sm:table-cell text-xs text-zinc-400">
                    {est.confidence != null ? `${(est.confidence * 100).toFixed(1)}%` : "—"}
                  </TableCell>
                  <TableCell className="text-right text-sm font-medium text-zinc-100">
                    {est.grand_total != null ? `LKR ${est.grand_total.toLocaleString()}` : "—"}
                  </TableCell>
                  <TableCell className="text-right">
                    <StatusBadge status={est.status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
    </div>
  );
}

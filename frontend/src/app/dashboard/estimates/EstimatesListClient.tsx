"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Plus, Square, RefreshCw, Trash2, Loader2, MoreHorizontal, Copy, Eye } from "lucide-react";
import {
  useEstimateList,
  useCancelEstimate,
  useRegenerateEstimate,
  useDeleteEstimate,
  useDuplicateEstimate,
} from "@/hooks/use-estimates";
import type { EstimateListItem } from "@/types/estimate";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

// ---------------------------------------------------------------------------
// Row action menu
// ---------------------------------------------------------------------------

function RowActions({ est, accessToken }: { est: EstimateListItem; accessToken: string }) {
  const router = useRouter();
  const [deleteOpen, setDeleteOpen] = useState(false);

  const cancelMutation = useCancelEstimate(accessToken);
  const regenerateMutation = useRegenerateEstimate(accessToken);
  const deleteMutation = useDeleteEstimate(accessToken);
  const duplicateMutation = useDuplicateEstimate(accessToken);

  const handleCancel = (e: React.MouseEvent) => {
    e.preventDefault();
    cancelMutation.mutate(est.id, {
      onSuccess: () => toast.success("Estimation cancelled"),
      onError: () => toast.error("Failed to cancel"),
    });
  };

  const handleRegenerate = (e: React.MouseEvent) => {
    e.preventDefault();
    regenerateMutation.mutate(est.id, {
      onSuccess: (data) => {
        toast.success("Regeneration started");
        router.push(`/dashboard/estimates/${data.id}`);
      },
      onError: () => toast.error("Failed to regenerate"),
    });
  };

  const handleDuplicate = (e: React.MouseEvent) => {
    e.preventDefault();
    duplicateMutation.mutate(est.id, {
      onSuccess: () => toast.success("Estimate duplicated"),
      onError: () => toast.error("Failed to duplicate"),
    });
  };

  const handleDelete = () => {
    deleteMutation.mutate(est.id, {
      onSuccess: () => toast.success("Estimate deleted"),
      onError: () => toast.error("Failed to delete"),
    });
  };

  if (est.status === "in_progress") {
    return (
      <div onClick={(e) => e.preventDefault()}>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="destructive"
                size="icon"
                onClick={handleCancel}
                disabled={cancelMutation.isPending}
              >
                {cancelMutation.isPending ? <Loader2 className="animate-spin" /> : <Square />}
              </Button>
            </TooltipTrigger>
            <TooltipContent>Stop estimation</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
    );
  }

  return (
    <div onClick={(e) => e.preventDefault()}>
      <DropdownMenu>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="text-muted-foreground">
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
            </TooltipTrigger>
            <TooltipContent>Actions</TooltipContent>
          </Tooltip>
        </TooltipProvider>

        <DropdownMenuContent align="end">
          <DropdownMenuItem asChild>
            <Link href={`/dashboard/estimates/${est.id}`}>
              <Eye className="mr-2 h-4 w-4" /> View
            </Link>
          </DropdownMenuItem>

          <DropdownMenuItem onClick={handleDuplicate} disabled={duplicateMutation.isPending}>
            {duplicateMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Copy className="mr-2 h-4 w-4" />
            )}
            Duplicate
          </DropdownMenuItem>

          {(est.status === "cancelled" || est.status === "failed") && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleRegenerate} disabled={regenerateMutation.isPending}>
                {regenerateMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="mr-2 h-4 w-4" />
                )}
                Regenerate
              </DropdownMenuItem>
            </>
          )}

          <DropdownMenuSeparator />
          <DropdownMenuItem
            className="text-destructive focus:text-destructive"
            onClick={(e) => {
              e.preventDefault();
              setDeleteOpen(true);
            }}
          >
            <Trash2 className="mr-2 h-4 w-4" /> Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete estimate?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete &quot;{est.project_name ?? "Untitled Project"}&quot;.
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? <Loader2 className="animate-spin" /> : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

// ---------------------------------------------------------------------------
// In-progress pulse indicator
// ---------------------------------------------------------------------------

function InProgressPulse() {
  return (
    <span className="relative mr-1 flex h-2 w-2 shrink-0">
      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
      <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-500" />
    </span>
  );
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function ListSkeleton() {
  return (
    <Card>
      <div className="divide-border divide-y">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center justify-between gap-4 px-4 py-4">
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-3 w-32" />
            </div>
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-5 w-16 rounded-full" />
          </div>
        ))}
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Main list component
// ---------------------------------------------------------------------------

export default function EstimatesListClient({ accessToken }: { accessToken: string }) {
  const { data, isLoading } = useEstimateList(accessToken, 1, 50);
  const estimates: EstimateListItem[] = data?.estimates ?? [];
  const hasActive = estimates.some((e) => e.status === "in_progress");
  const activeCount = estimates.filter((e) => e.status === "in_progress").length;

  if (isLoading) return <ListSkeleton />;

  if (estimates.length === 0) {
    return (
      <Card className="border-border/60 bg-card/80 py-16 text-center">
        <p className="mb-4 text-sm text-zinc-400">No estimates yet.</p>
        <Button asChild className="bg-blue-600 text-white hover:bg-blue-500">
          <Link href="/dashboard/estimate/new">
            <Plus /> Create your first estimate
          </Link>
        </Button>
      </Card>
    );
  }

  return (
    <Card className="border-border/60 bg-card/80 overflow-hidden backdrop-blur-sm">
      {/* Active run banner */}
      {hasActive && (
        <div className="flex items-center gap-2 border-b border-blue-500/20 bg-blue-500/10 px-4 py-2 text-xs text-blue-400">
          <InProgressPulse />
          {activeCount} estimate{activeCount > 1 ? "s" : ""} running — auto-refreshing...
        </div>
      )}

      {/* Table header */}
      <div className="border-border/60 grid grid-cols-[1fr_auto_auto_auto_auto] gap-4 border-b px-4 py-2.5 text-xs font-medium tracking-wide text-zinc-500 uppercase">
        <div>Project</div>
        <div className="text-right">Items</div>
        <div className="text-right">Grand Total</div>
        <div className="text-right">Status</div>
        <div className="w-10" />
      </div>

      {/* Rows */}
      <div className="divide-border/40 divide-y">
        {estimates.map((est) => (
          <div
            key={est.id}
            className="group grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-4 px-4 py-3.5 transition-colors hover:bg-white/5"
          >
            <Link href={`/dashboard/estimates/${est.id}`} className="min-w-0">
              <div className="flex items-center gap-2">
                {est.status === "in_progress" && <InProgressPulse />}
                <p className="truncate text-sm font-medium text-zinc-100">
                  {est.project_name ?? "Untitled Project"}
                </p>
              </div>
              <p className="mt-0.5 text-xs text-zinc-500">
                {new Date(est.created_at).toLocaleDateString()} ·{" "}
                {est.confidence != null ? `${(est.confidence * 100).toFixed(1)}% confidence` : "—"}
              </p>
            </Link>
            <Link
              href={`/dashboard/estimates/${est.id}`}
              className="text-right text-sm text-zinc-400"
            >
              {est.item_count ?? "—"}
            </Link>
            <Link
              href={`/dashboard/estimates/${est.id}`}
              className="text-right text-sm font-medium text-zinc-100"
            >
              {est.grand_total != null ? `LKR ${est.grand_total.toLocaleString()}` : "—"}
            </Link>
            <Link href={`/dashboard/estimates/${est.id}`} className="text-right">
              <StatusBadge status={est.status} />
            </Link>
            <div className="flex w-10 justify-end">
              <RowActions est={est} accessToken={accessToken} />
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

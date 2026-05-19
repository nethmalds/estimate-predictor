"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import dynamic from "next/dynamic";
import type { BoqItem } from "@/components/results/ResultsComponents";

const CostBreakdownChart = dynamic(
  () => import("@/components/results/ResultsComponents").then((m) => m.CostBreakdownChart),
  { loading: () => <div className="bg-muted h-64 animate-pulse rounded-lg" /> }
);
const ConfidenceBreakdownCard = dynamic(
  () => import("@/components/results/ResultsComponents").then((m) => m.ConfidenceBreakdownCard),
  { loading: () => <div className="bg-muted h-32 animate-pulse rounded-lg" /> }
);
const FullBoqTable = dynamic(
  () => import("@/components/results/ResultsComponents").then((m) => m.FullBoqTable),
  { loading: () => <div className="bg-muted h-64 animate-pulse rounded-lg" /> }
);

async function downloadExcelBlob(data: Record<string, unknown>): Promise<void> {
  const { downloadExcelBlob: fn } = await import("@/components/results/ResultsComponents");
  fn(data);
}
import {
  Download,
  FileText,
  TrendingUp,
  DollarSign,
  Edit3,
  Check,
  X,
  Square,
  RefreshCw,
  Trash2,
  XCircle,
  Clock,
  CheckCircle2,
  Loader2,
  Minus,
  ChevronDown,
  ChevronUp,
  Building2,
  Layers,
  Hammer,
  MapPin,
  AlertCircle,
} from "lucide-react";
import { patchEstimate } from "@/services/estimates.service";
import {
  useEstimateDetail,
  useCancelEstimate,
  useRegenerateEstimate,
  useDeleteEstimate,
} from "@/hooks/use-estimates";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

// ---------------------------------------------------------------------------
// Pipeline stage definitions
// ---------------------------------------------------------------------------

const PIPELINE_STAGES = [
  { key: "floorplan_cv", label: "Floor Plan Analysis", optional: true },
  { key: "floorplan_acceptance", label: "Plan Acceptance Check", optional: true },
  { key: "baseline_boq", label: "BOQ Generation" },
  { key: "boq_validation", label: "BOQ Validation" },
  { key: "bsr_matching", label: "BSR Rate Matching" },
  { key: "bsr_validation", label: "Rate Validation" },
  { key: "quantity_takeoff", label: "Quantity Take-Off" },
  { key: "validation", label: "Quantity Validation" },
  { key: "cost_calculation", label: "Cost Calculation" },
  { key: "transparency", label: "Confidence Analysis" },
  { key: "reporting", label: "Report Generation" },
] as const;

type StageKey = (typeof PIPELINE_STAGES)[number]["key"];

function getStageStatus(
  key: StageKey,
  progressSteps: ProgressStep[]
): "completed" | "active" | "pending" | "failed" | "skipped" {
  const step = [...progressSteps].reverse().find((s) => s.step === key);
  if (!step) return "pending";
  if (step.status === "skipped") return "skipped";
  if (step.status === "completed" || step.status === "accepted" || step.status === "done")
    return "completed";
  if (step.status === "rejected" || step.status === "failed") return "failed";
  return "active";
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ProgressStep {
  step: string;
  status: string;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// Elapsed time hook
// ---------------------------------------------------------------------------

function useElapsedTime(started: string, running: boolean) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!running) return;
    const start = new Date(started).getTime();
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - start) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [running, started]);
  return elapsed;
}

function formatTime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

// ---------------------------------------------------------------------------
// Progress timeline — semantic tokens
// ---------------------------------------------------------------------------

function ProgressStageTimeline({ progressSteps }: { progressSteps: ProgressStep[] }) {
  const completedCount = PIPELINE_STAGES.filter(
    (s) => getStageStatus(s.key, progressSteps) === "completed"
  ).length;
  const countableStages = PIPELINE_STAGES.filter(
    (s) => getStageStatus(s.key, progressSteps) !== "skipped"
  ).length;
  const percent = Math.round((completedCount / (countableStages || PIPELINE_STAGES.length)) * 100);

  return (
    <div className="space-y-3">
      <div className="mb-4 flex items-center gap-3">
        <Progress value={percent} className="flex-1" />
        <span className="min-w-9 text-right font-mono text-xs text-blue-400">{percent}%</span>
      </div>

      <div className="grid grid-cols-1 gap-1.5">
        {PIPELINE_STAGES.map((stage) => {
          const status = getStageStatus(stage.key, progressSteps);
          return (
            <div
              key={stage.key}
              className={`flex items-center gap-3 rounded-lg border px-3 py-2 transition-all ${
                status === "active"
                  ? "border-blue-500/20 bg-blue-500/10"
                  : status === "completed"
                    ? "bg-muted/40 border-transparent"
                    : status === "failed"
                      ? "bg-destructive/10 border-destructive/20"
                      : status === "skipped"
                        ? "bg-muted/20 border-transparent opacity-60"
                        : "bg-muted/40 border-transparent"
              }`}
            >
              <span
                className={`shrink-0 ${
                  status === "completed"
                    ? "text-green-400"
                    : status === "active"
                      ? "text-blue-400"
                      : status === "failed"
                        ? "text-destructive"
                        : status === "skipped"
                          ? "text-zinc-400"
                          : "text-muted-foreground"
                }`}
              >
                {status === "completed" ? (
                  <CheckCircle2 className="h-4 w-4" />
                ) : status === "active" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : status === "failed" ? (
                  <XCircle className="h-4 w-4" />
                ) : status === "skipped" ? (
                  <Minus className="h-4 w-4" />
                ) : (
                  <div className="border-border h-4 w-4 rounded-full border-2" />
                )}
              </span>
              <span
                className={`text-xs ${
                  status === "active"
                    ? "text-foreground font-medium"
                    : status === "completed"
                      ? "text-foreground/80"
                      : status === "failed"
                        ? "text-destructive"
                        : status === "skipped"
                          ? "text-muted-foreground/60 italic"
                          : "text-muted-foreground"
                }`}
              >
                {stage.label}
                {"optional" in stage && (
                  <span className="text-muted-foreground ml-1">(optional)</span>
                )}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Project Specification Panel
// ---------------------------------------------------------------------------

function ProjectSpecPanel({ wizardPayload }: { wizardPayload: Record<string, unknown> }) {
  const [open, setOpen] = useState(false);

  const buildingType = wizardPayload.building_type as string | undefined;
  const floorCount = wizardPayload.floor_count as string | number | undefined;
  const floorAreas = wizardPayload.floor_areas as
    | Array<{ floor_label: string; area_value: number }>
    | undefined;
  const finishLevel = wizardPayload.finish_level as string | undefined;
  const structuralSystem = wizardPayload.structural_system as string | undefined;
  const roofType = wizardPayload.roof_type as string | undefined;
  const location = wizardPayload.location as string | undefined;
  const description = wizardPayload.description as string | undefined;
  const floorplanUrls = wizardPayload.floorplan_urls as string[] | undefined;

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <Card className="border-border/60 bg-card/80 mb-6 overflow-hidden backdrop-blur-sm">
        <CollapsibleTrigger asChild>
          <Button
            variant="ghost"
            className="flex h-auto w-full items-center justify-between rounded-none px-5 py-4 hover:bg-white/5"
          >
            <div className="flex items-center gap-2">
              <Building2 className="h-4 w-4 text-zinc-400" />
              <span className="text-sm font-medium text-zinc-900">Project Specification</span>
            </div>
            {open ? (
              <ChevronUp className="h-4 w-4 text-zinc-400" />
            ) : (
              <ChevronDown className="h-4 w-4 text-zinc-400" />
            )}
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="border-border/60 grid grid-cols-2 gap-x-8 gap-y-3 border-t px-5 pt-4 pb-5 text-sm">
            {buildingType && (
              <div className="flex items-center gap-2">
                <Building2 className="text-muted-foreground h-3.5 w-3.5" />
                <span className="text-muted-foreground capitalize">{buildingType}</span>
              </div>
            )}
            {floorCount && (
              <div className="flex items-center gap-2">
                <Layers className="text-muted-foreground h-3.5 w-3.5" />
                <span className="text-muted-foreground">
                  {floorCount} floor{Number(floorCount) !== 1 ? "s" : ""}
                </span>
              </div>
            )}
            {finishLevel && (
              <div className="flex items-center gap-2">
                <Hammer className="text-muted-foreground h-3.5 w-3.5" />
                <span className="text-muted-foreground capitalize">{finishLevel} finish</span>
              </div>
            )}
            {structuralSystem && (
              <div className="flex items-center gap-2">
                <Building2 className="text-muted-foreground h-3.5 w-3.5" />
                <span className="text-muted-foreground capitalize">{structuralSystem}</span>
              </div>
            )}
            {roofType && (
              <div className="flex items-center gap-2">
                <Building2 className="text-muted-foreground h-3.5 w-3.5" />
                <span className="text-muted-foreground capitalize">{roofType} roof</span>
              </div>
            )}
            {location && (
              <div className="flex items-center gap-2">
                <MapPin className="text-muted-foreground h-3.5 w-3.5" />
                <span className="text-muted-foreground capitalize">{location}</span>
              </div>
            )}
            {description && (
              <div className="col-span-2">
                <p className="text-muted-foreground text-xs">{description}</p>
              </div>
            )}
            {floorAreas && floorAreas.length > 0 && (
              <div className="col-span-2">
                <p className="text-muted-foreground mb-1 text-xs">Floor Areas</p>
                <div className="flex flex-wrap gap-2">
                  {floorAreas.map((fa) => (
                    <span
                      key={fa.floor_label}
                      className="bg-muted text-muted-foreground rounded px-2 py-0.5 text-xs"
                    >
                      {fa.floor_label}: {fa.area_value} m²
                    </span>
                  ))}
                </div>
              </div>
            )}
            {floorplanUrls && floorplanUrls.length > 0 && (
              <div className="col-span-2">
                <p className="text-muted-foreground text-xs">
                  {floorplanUrls.length} floor plan image{floorplanUrls.length > 1 ? "s" : ""}{" "}
                  uploaded
                </p>
              </div>
            )}
          </div>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function EstimateDetailClient({
  estimateId,
  accessToken,
}: {
  estimateId: string;
  accessToken: string;
}) {
  const router = useRouter();
  const { data: estimate } = useEstimateDetail(accessToken, estimateId);
  const cancelMutation = useCancelEstimate(accessToken);
  const regenerateMutation = useRegenerateEstimate(accessToken);
  const deleteMutation = useDeleteEstimate(accessToken);

  const [projectName, setProjectName] = useState("");
  const [notes, setNotes] = useState("");
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (estimate) {
      setProjectName(estimate.project_name ?? "");
      setNotes(estimate.notes ?? "");
    }
  }, [estimate?.id]);

  const elapsed = useElapsedTime(
    estimate?.created_at ?? new Date().toISOString(),
    estimate?.status === "in_progress"
  );

  if (!estimate) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-14 w-full rounded-xl" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }

  const result = estimate.result ?? {};
  const costs = (result.costs as Record<string, unknown>) ?? {};
  const confidence = (result.confidence as Record<string, unknown>) ?? {};
  const boqItems = (result.boq_items as BoqItem[]) ?? [];
  const subtotals = (costs.subtotals as Record<string, number>) ?? {};
  const grandTotal = Number(costs.total ?? estimate.grand_total ?? 0);
  const progressSteps: ProgressStep[] =
    ((estimate.progress as Record<string, unknown>)?.steps as ProgressStep[]) ?? [];
  const wizardPayload = estimate.wizard_payload as Record<string, unknown> | null;

  const saveEdits = async () => {
    setSaving(true);
    try {
      await patchEstimate(estimate.id, { project_name: projectName, notes }, accessToken);
      setEditing(false);
      toast.success("Changes saved");
    } catch {
      toast.error("Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    cancelMutation.mutate(estimate.id, {
      onSuccess: () => toast.success("Estimation cancelled"),
      onError: () => toast.error("Failed to cancel"),
    });
  };

  const handleRegenerate = () => {
    regenerateMutation.mutate(estimate.id, {
      onSuccess: (data) => {
        toast.success("Regeneration started");
        router.push(`/dashboard/estimates/${data.id}`);
      },
      onError: () => toast.error("Failed to regenerate"),
    });
  };

  const handleDelete = () => {
    deleteMutation.mutate(estimate.id, {
      onSuccess: () => {
        toast.success("Estimate deleted");
        router.push("/dashboard/estimates");
      },
      onError: () => toast.error("Failed to delete"),
    });
  };

  // ── In-Progress view ────────────────────────────────────────────────────

  if (estimate.status === "in_progress") {
    return (
      <div className="space-y-6">
        {wizardPayload && <ProjectSpecPanel wizardPayload={wizardPayload} />}

        <Card className="border-border/60 bg-card/80 overflow-hidden backdrop-blur-sm">
          <div className="bg-muted relative h-1.5 overflow-hidden">
            <div className="absolute inset-0 animate-pulse bg-linear-to-r from-blue-600 via-blue-400 to-blue-600" />
          </div>

          <CardContent className="p-6">
            <div className="mb-6 flex items-start justify-between">
              <div>
                <h3 className="text-base font-semibold text-zinc-900">Estimation in Progress</h3>
                <p className="mt-0.5 text-sm text-zinc-400">
                  AI is analysing your project and generating the BOQ...
                </p>
              </div>
              <div className="flex items-center gap-2 rounded-lg bg-zinc-100/60 px-3 py-1.5">
                <Clock className="h-3.5 w-3.5 text-zinc-400" />
                <span className="font-mono text-sm text-zinc-900">{formatTime(elapsed)}</span>
              </div>
            </div>

            <ProgressStageTimeline progressSteps={progressSteps} />

            <div className="border-border mt-6 flex items-center justify-between border-t pt-5">
              <p className="text-muted-foreground text-xs">
                You can leave this page — estimation continues in the background.
              </p>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="destructive"
                      onClick={handleCancel}
                      disabled={cancelMutation.isPending}
                    >
                      {cancelMutation.isPending ? (
                        <>
                          <Loader2 className="animate-spin" /> Stopping...
                        </>
                      ) : (
                        <>
                          <Square /> Stop Estimation
                        </>
                      )}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Stop the estimation run</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ── Cancelled / Failed view ─────────────────────────────────────────────

  if (estimate.status === "cancelled" || estimate.status === "failed") {
    const isCancelled = estimate.status === "cancelled";
    return (
      <div className="space-y-6">
        {wizardPayload && <ProjectSpecPanel wizardPayload={wizardPayload} />}

        <Card>
          <CardContent className="p-8 text-center">
            {isCancelled ? (
              <XCircle className="mx-auto mb-4 h-12 w-12 text-amber-400" />
            ) : (
              <AlertCircle className="text-destructive mx-auto mb-4 h-12 w-12" />
            )}
            <h3 className="mb-2 text-lg font-semibold">
              {isCancelled ? "Estimation Stopped" : "Estimation Failed"}
            </h3>
            <p className="text-muted-foreground mb-1 text-sm">
              {isCancelled
                ? "You stopped this estimation run."
                : "An error occurred during estimation."}
            </p>

            {estimate.error_message && (
              <div className="mx-auto mt-4 max-w-lg">
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertTitle>Error details</AlertTitle>
                  <AlertDescription>{estimate.error_message}</AlertDescription>
                </Alert>
              </div>
            )}

            <div className="mt-6 flex items-center justify-center gap-3">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      onClick={handleRegenerate}
                      disabled={regenerateMutation.isPending || !estimate.wizard_payload}
                    >
                      {regenerateMutation.isPending ? (
                        <>
                          <Loader2 className="animate-spin" /> Starting...
                        </>
                      ) : (
                        <>
                          <RefreshCw /> Regenerate Estimate
                        </>
                      )}
                    </Button>
                  </TooltipTrigger>
                  {!estimate.wizard_payload && (
                    <TooltipContent>Unavailable — no wizard data stored</TooltipContent>
                  )}
                </Tooltip>
              </TooltipProvider>

              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant="outline">
                    <Trash2 /> Delete
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Delete estimate?</AlertDialogTitle>
                    <AlertDialogDescription>
                      This will permanently delete this estimate. This action cannot be undone.
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

            {!estimate.wizard_payload && (
              <p className="text-muted-foreground mt-3 text-xs">
                Regenerate is unavailable — no wizard data was stored for this estimate.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  // ── Completed view ──────────────────────────────────────────────────────

  const summaryCards = [
    {
      label: "Grand Total",
      value: `LKR ${grandTotal.toLocaleString()}`,
      icon: <DollarSign className="h-5 w-5 text-blue-400" />,
    },
    {
      label: "Confidence Score",
      value: `${(Number(confidence.score ?? estimate.confidence ?? 0) * 100).toFixed(1)}%`,
      icon: <TrendingUp className="h-5 w-5 text-green-400" />,
    },
    {
      label: "BOQ Items",
      value: boqItems.length || estimate.item_count || 0,
      icon: <FileText className="h-5 w-5 text-purple-400" />,
    },
  ];

  return (
    <div className="space-y-6">
      {wizardPayload && <ProjectSpecPanel wizardPayload={wizardPayload} />}

      {/* ── Metadata edit ── */}
      <Card className="border-border/60 bg-card/80 backdrop-blur-sm">
        <CardContent className="p-5">
          {editing ? (
            <div className="space-y-3">
              <div>
                <Label className="mb-1 text-xs text-zinc-400">Project name</Label>
                <Input value={projectName} onChange={(e) => setProjectName(e.target.value)} />
              </div>
              <div>
                <Label className="mb-1 text-xs text-zinc-400">Notes</Label>
                <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} />
              </div>
              <div className="flex gap-2">
                <Button size="sm" onClick={saveEdits} disabled={saving}>
                  <Check /> Save
                </Button>
                <Button size="sm" variant="outline" onClick={() => setEditing(false)}>
                  <X /> Cancel
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-medium text-zinc-900">
                  {projectName || "Untitled Project"}
                </p>
                {notes && <p className="mt-1 text-xs text-zinc-400">{notes}</p>}
              </div>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setEditing(true)}
                      className="text-zinc-400 hover:text-zinc-900"
                    >
                      <Edit3 /> Edit
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Edit project name and notes</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Summary cards ── */}
      <div className="grid grid-cols-3 gap-4">
        {summaryCards.map((c) => (
          <Card key={c.label} className="border-border/60 bg-card/80 backdrop-blur-sm">
            <CardContent className="p-4">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-xs text-zinc-400">{c.label}</p>
                {c.icon}
              </div>
              <p className="text-xl font-bold text-zinc-900">{c.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* ── Confidence breakdown ── */}
      {Object.keys(confidence).length > 0 && <ConfidenceBreakdownCard confidence={confidence} />}

      {/* ── Cost breakdown chart ── */}
      {Object.keys(subtotals).length > 0 && <CostBreakdownChart subtotals={subtotals} />}

      {/* ── Full BOQ table ── */}
      {boqItems.length > 0 ? (
        <FullBoqTable items={boqItems} grandTotal={grandTotal} />
      ) : (
        <Card className="border-border/60 bg-card/80">
          <CardContent className="p-8 text-center text-sm text-zinc-400">
            No BOQ items available for this estimate.
          </CardContent>
        </Card>
      )}

      {/* ── Actions bar ── */}
      <div className="flex flex-wrap items-center gap-3 pt-2">
        {result && boqItems.length > 0 && (
          <Button
            onClick={() => downloadExcelBlob(result)}
            className="bg-blue-600 text-white hover:bg-blue-500"
          >
            <Download /> Download Excel Report
          </Button>
        )}

        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                onClick={handleRegenerate}
                disabled={regenerateMutation.isPending || !estimate.wizard_payload}
              >
                {regenerateMutation.isPending ? (
                  <>
                    <Loader2 className="animate-spin" /> Starting...
                  </>
                ) : (
                  <>
                    <RefreshCw /> Regenerate
                  </>
                )}
              </Button>
            </TooltipTrigger>
            {!estimate.wizard_payload && (
              <TooltipContent>Regenerate unavailable — no wizard data stored</TooltipContent>
            )}
          </Tooltip>
        </TooltipProvider>

        <div className="ml-auto">
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="text-muted-foreground hover:text-destructive"
              >
                <Trash2 /> Delete
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete estimate?</AlertDialogTitle>
                <AlertDialogDescription>
                  This will permanently delete &quot;{projectName || "Untitled Project"}&quot;. This
                  action cannot be undone.
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
      </div>
    </div>
  );
}

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { EstimateStatus } from "@/types/estimate";

const STATUS_STYLES: Record<EstimateStatus, string> = {
  completed: "bg-green-500/15 text-green-400 border-green-500/25 hover:bg-green-500/15",
  in_progress: "bg-blue-500/15 text-blue-400 border-blue-500/25 hover:bg-blue-500/15",
  failed: "bg-red-500/15 text-red-400 border-red-500/25 hover:bg-red-500/15",
  cancelled: "bg-amber-500/15 text-amber-400 border-amber-500/25 hover:bg-amber-500/15",
};

export function StatusBadge({ status }: { status: EstimateStatus | string }) {
  return (
    <Badge variant="outline" className={cn("capitalize", STATUS_STYLES[status as EstimateStatus])}>
      {status.replace("_", " ")}
    </Badge>
  );
}

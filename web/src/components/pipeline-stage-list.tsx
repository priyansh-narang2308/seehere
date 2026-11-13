import { CheckCircle2, Circle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { type PipelineStage, pipelineStages } from "@/lib/pipeline";

/** Ordered list of pipeline stages with their honest build status. */
export function PipelineStageList({ stages = pipelineStages }: { stages?: readonly PipelineStage[] }) {
  return (
    <ol className="divide-y divide-border rounded-lg border border-border bg-surface shadow-card">
      {stages.map((stage, i) => {
        const built = stage.status === "built";
        return (
          <li key={stage.id} className="flex gap-4 px-4 py-4 sm:px-5">
            <span className="mt-0.5 font-mono text-xs text-muted tabular-nums" aria-hidden="true">
              {String(i + 1).padStart(2, "0")}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-ink">{stage.name}</span>
                {stage.optional && <Badge>Optional</Badge>}
              </div>
              <p className="mt-1 text-sm text-muted">{stage.summary}</p>
            </div>
            <Badge tone={built ? "success" : "neutral"} className="h-fit shrink-0">
              {built ? <CheckCircle2 aria-hidden="true" /> : <Circle aria-hidden="true" />}
              {built ? "Built" : "Not built yet"}
            </Badge>
          </li>
        );
      })}
    </ol>
  );
}

import { Badge } from "@/components/ui/badge";
import type { ProjectStatus } from "@/lib/api";

const STATUS = {
  uploaded: { label: "Uploaded", tone: "accent" },
  processing: { label: "Processing", tone: "warning" },
  ready: { label: "Ready", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
} as const satisfies Record<ProjectStatus, { label: string; tone: "accent" | "warning" | "success" | "danger" }>;

export function ProjectStatusBadge({ status }: { status: ProjectStatus }) {
  const s = STATUS[status];
  return <Badge tone={s.tone}>{s.label}</Badge>;
}

import { ListChecks } from "lucide-react";
import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/page";
import { EmptyState } from "@/components/ui/empty-state";

export const metadata: Metadata = { title: "Results" };

export default function ResultsPage() {
  return (
    <>
      <PageHeader
        title="Results"
        description="Descriptions with their evidence and verification state, ready for review and export."
      />
      <EmptyState
        className="mt-8"
        icon={ListChecks}
        title="No results yet"
        description="Results appear after processing finishes. The processing pipeline is not built yet, so this project has none."
      />
    </>
  );
}

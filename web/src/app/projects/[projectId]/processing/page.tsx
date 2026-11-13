import { Activity } from "lucide-react";
import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/page";
import { PipelineStageList } from "@/components/pipeline-stage-list";
import { EmptyState } from "@/components/ui/empty-state";

export const metadata: Metadata = { title: "Processing" };

export default function ProcessingPage() {
  return (
    <>
      <PageHeader title="Processing" description="Live progress for each stage of this lecture's analysis." />
      <EmptyState
        className="mt-8"
        icon={Activity}
        title="No processing data"
        description="Project storage and the processing pipeline are not built yet, so there is nothing to track for this project."
      />
      <section aria-labelledby="stages" className="mt-10">
        <h2 id="stages" className="text-lg font-semibold tracking-tight text-ink">
          Stages this page will track
        </h2>
        <div className="mt-4">
          <PipelineStageList />
        </div>
      </section>
    </>
  );
}

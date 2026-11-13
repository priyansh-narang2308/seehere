import { Activity } from "lucide-react";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { PageHeader } from "@/components/layout/page";
import { PipelineStageList } from "@/components/pipeline-stage-list";
import { SourceFacts } from "@/components/project/source-facts";
import { EmptyState } from "@/components/ui/empty-state";
import { getProject } from "@/lib/projects.server";

export const metadata: Metadata = { title: "Processing" };

export default function ProcessingPage({ params }: PageProps<"/projects/[projectId]/processing">) {
  return (
    <>
      <PageHeader title="Processing" description="Progress for each stage of this lecture's analysis." />
      <div className="mt-8 space-y-6">
        <Suspense fallback={<div className="h-40 rounded-lg border border-border bg-surface-muted" aria-hidden="true" />}>
          <UploadedSource params={params} />
        </Suspense>
        <EmptyState
          icon={Activity}
          title="Analysis has not started"
          description="The upload is stored and checked. The analysis stages after upload are not built yet, so nothing runs next."
        />
      </div>
      <section aria-labelledby="stages" className="mt-10">
        <h2 id="stages" className="text-lg font-semibold tracking-tight text-ink">
          Pipeline stages
        </h2>
        <div className="mt-4">
          <PipelineStageList />
        </div>
      </section>
    </>
  );
}

async function UploadedSource({ params }: { params: Promise<{ projectId: string }> }) {
  const project = await getProject((await params).projectId);
  if (!project) notFound();
  return <SourceFacts project={project} />;
}

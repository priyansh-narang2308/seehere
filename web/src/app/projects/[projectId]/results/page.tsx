import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { PageHeader } from "@/components/layout/page";
import { ResultsView } from "@/components/project/results-view";
import { getProject } from "@/lib/projects.server";

export const metadata: Metadata = { title: "Results" };

export default function ResultsPage({ params }: PageProps<"/projects/[projectId]/results">) {
  return (
    <>
      <PageHeader
        title="Results"
        description="Watch the lecture with its audio descriptions, then download the files to publish."
      />
      <Suspense fallback={<p className="mt-8 text-sm text-muted">Loading results…</p>}>
        <Results params={params} />
      </Suspense>
    </>
  );
}

async function Results({ params }: { params: Promise<{ projectId: string }> }) {
  const project = await getProject((await params).projectId);
  if (!project) notFound();
  return <ResultsView projectId={project.id} title={project.title} />;
}

import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { Container } from "@/components/layout/page";
import { ProjectTabs } from "@/components/project/project-tabs";
import { getProject } from "@/lib/projects.server";

export default function ProjectLayout({ children, params }: LayoutProps<"/projects/[projectId]">) {
  return (
    <Container className="py-10">
      {/* Project IDs are only known at request time, so read params inside Suspense
          (Next.js Cache Components). The page content below stays prerendered. */}
      <Suspense fallback={<div className="h-[76px]" aria-hidden="true" />}>
        <ProjectNav params={params} />
      </Suspense>
      <div className="mt-8">{children}</div>
    </Container>
  );
}

async function ProjectNav({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  const project = await getProject(projectId);
  if (!project) notFound();

  return (
    <div className="space-y-5">
      <nav aria-label="Breadcrumb">
        <ol className="flex flex-wrap items-center gap-1.5 text-sm text-muted">
          <li>
            <Link href="/projects" className="font-medium text-ink-2 underline-offset-4 hover:text-ink hover:underline">
              Projects
            </Link>
          </li>
          <li aria-hidden="true">
            <ChevronRight className="size-3.5" />
          </li>
          <li>
            <span aria-current="location" className="font-medium text-ink">
              {project.title}
            </span>
          </li>
        </ol>
      </nav>
      <ProjectTabs projectId={project.id} />
    </div>
  );
}

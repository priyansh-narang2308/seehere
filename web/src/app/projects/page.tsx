import { FolderOpen, Upload } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { Container, PageHeader } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

export const metadata: Metadata = {
  title: "Projects",
  description: "Your lecture videos and their audio description projects.",
};

export default function ProjectsPage() {
  return (
    <Container className="py-12">
      <PageHeader
        title="Projects"
        description="Each uploaded lecture becomes a project: its processing progress, descriptions, evidence and exports."
        actions={
          <Button asChild>
            <Link href="/upload">
              <Upload aria-hidden="true" /> Upload lecture
            </Link>
          </Button>
        }
      />
      <EmptyState
        className="mt-8"
        icon={FolderOpen}
        title="No projects yet"
        description="Projects appear here after you upload a lecture. Project storage and uploads are not built yet, so this list is empty."
      />
    </Container>
  );
}

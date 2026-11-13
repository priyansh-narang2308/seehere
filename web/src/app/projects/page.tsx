import { Upload } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { Container, PageHeader } from "@/components/layout/page";
import { ProjectList } from "@/components/project/project-list";
import { Button } from "@/components/ui/button";

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
      <ProjectList />
    </Container>
  );
}

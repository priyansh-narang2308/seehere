import { SearchX } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { Container } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

export const metadata: Metadata = { title: "Page not found" };

export default function NotFound() {
  return (
    <Container className="py-16">
      <h1 className="sr-only">Page not found</h1>
      <EmptyState
        icon={SearchX}
        title="We couldn't find that page"
        description="The link may be mistyped, or the project may not exist."
      >
        <Button asChild>
          <Link href="/">Go to home</Link>
        </Button>
        <Button asChild variant="secondary">
          <Link href="/projects">View projects</Link>
        </Button>
      </EmptyState>
    </Container>
  );
}

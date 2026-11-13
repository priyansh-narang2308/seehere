"use client";

import { TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";
import { Container } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

/** Route-level error boundary. Shows a plain message, never the raw error, and offers a retry. */
export default function RouteError({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <Container className="py-16">
      <h1 className="sr-only">Something went wrong</h1>
      <div role="alert">
        <EmptyState
          icon={TriangleAlert}
          title="Something went wrong on this page"
          description="The error has been logged in the browser console. Try again, or go back to the home page."
        >
          <Button onClick={() => retry()}>Try again</Button>
          <Button asChild variant="secondary">
            <Link href="/">Go to home</Link>
          </Button>
        </EmptyState>
      </div>
    </Container>
  );
}

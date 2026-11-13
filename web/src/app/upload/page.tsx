import { FileVideo } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { Container, PageHeader } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

export const metadata: Metadata = {
  title: "Upload a lecture",
  description: "Upload a lecture video to generate evidence-grounded audio descriptions.",
};

const requirements = [
  "A lecture video that you own, or have permission to process.",
  "Optionally, the slide deck as PDF or PPTX, to improve text matching.",
  "Time to review: every description is checked by a person before it is published.",
];

export default function UploadPage() {
  return (
    <Container className="py-12">
      <PageHeader
        title="Upload a lecture"
        description="SeeHere analyzes the video's speech, frames and on-screen text, then drafts descriptions for you to review."
      />

      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_320px]">
        <EmptyState
          icon={FileVideo}
          title="Uploads are not open in this build yet"
          description="The secure upload flow is being built next. This page does not accept files yet."
        >
          <Button asChild variant="secondary">
            <Link href="/methodology">See what is built</Link>
          </Button>
        </EmptyState>

        <section aria-labelledby="needs" className="rounded-lg border border-border bg-surface p-5 shadow-card">
          <h2 id="needs" className="font-semibold text-ink">
            What you will need
          </h2>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-ink-2 marker:text-muted">
            {requirements.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </section>
      </div>
    </Container>
  );
}

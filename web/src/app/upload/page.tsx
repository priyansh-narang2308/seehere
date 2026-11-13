import type { Metadata } from "next";
import { Container, PageHeader } from "@/components/layout/page";
import { UploadForm } from "./upload-form";

export const metadata: Metadata = {
  title: "Upload a lecture",
  description: "Upload a lecture video to generate evidence-grounded audio descriptions.",
};

export default function UploadPage() {
  return (
    <Container className="py-12">
      <PageHeader
        title="Upload a lecture"
        description="SeeHere checks the file, stores it privately and creates a project for it."
      />
      <div className="mt-8">
        <UploadForm />
      </div>
    </Container>
  );
}

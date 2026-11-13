import type { Metadata } from "next";
import { BackendStatus } from "@/components/BackendStatus";
import { Container, PageHeader } from "@/components/layout/page";

export const metadata: Metadata = {
  title: "System status",
  description: "Live health of the SeeHere API, database and media tools.",
};

export default function StatusPage() {
  return (
    <Container className="py-12">
      <PageHeader
        title="System status"
        description="Live readiness of the API and the tools it depends on. AI providers show as untested until a real request has succeeded."
      />
      <div className="mt-8">
        <BackendStatus />
      </div>
    </Container>
  );
}

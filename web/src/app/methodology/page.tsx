import type { Metadata } from "next";
import { Container, PageHeader } from "@/components/layout/page";
import { PipelineStageList } from "@/components/pipeline-stage-list";
import { VERIFICATION_STATES, VerificationBadge, type VerificationState } from "@/components/ui/verification-badge";
import { countBuilt, pipelineStages } from "@/lib/pipeline";

export const metadata: Metadata = {
  title: "Methodology",
  description: "How SeeHere turns a lecture video into evidence-grounded audio descriptions, and its limits.",
};

const limits = [
  "A verified text match means quoted text or numbers were found on screen by OCR. It does not prove that a description of a chart's meaning is correct.",
  "OCR and vision models make mistakes. Low-confidence or ambiguous findings are marked for human review rather than guessed.",
  "SeeHere supports accessibility work. It does not certify that a video meets WCAG or any other standard.",
  "Descriptions are drafts until an instructor approves them.",
];

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id} className="mt-14">
      <h2 id={id} className="text-xl font-semibold tracking-tight text-ink">
        {title}
      </h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export default function MethodologyPage() {
  const built = countBuilt();
  return (
    <Container className="py-12">
      <PageHeader
        eyebrow="Methodology"
        title="How SeeHere works"
        description="From a lecture video to audio descriptions you can check, step by step, including what the system cannot do."
      />

      <Section id="problem" title="The problem">
        <div className="max-w-3xl space-y-3 text-ink-2">
          <p>
            Lecturers point at things: “notice this blue line here”, “as you can see, it peaks in week three”. A
            student who cannot see the screen hears the words but misses the picture.
          </p>
          <p>
            SeeHere looks for those moments, and for visuals that are never mentioned at all, and writes short spoken
            descriptions that fit into the pauses in the lecturer’s speech.
          </p>
        </div>
      </Section>

      <Section id="pipeline" title="The pipeline">
        <p className="mb-4 text-sm text-muted">
          {built} of {pipelineStages.length} stages are built in this version. Stages are marked built only once they
          are implemented and tested.
        </p>
        <PipelineStageList />
      </Section>

      <Section id="verification" title="Verification states">
        <p className="mb-4 max-w-3xl text-ink-2">
          Every description carries exactly one of these states, based on the evidence behind it.
        </p>
        <dl className="grid gap-3 sm:grid-cols-2">
          {(Object.entries(VERIFICATION_STATES) as [VerificationState, (typeof VERIFICATION_STATES)[VerificationState]][]).map(
            ([key, v]) => (
              <div key={key} className="rounded-lg border border-border bg-surface p-4 shadow-card">
                <dt>
                  <VerificationBadge state={key} />
                </dt>
                <dd className="mt-2 text-sm text-ink-2">{v.help}</dd>
              </div>
            ),
          )}
        </dl>
      </Section>

      <Section id="modes" title="Standard and extended descriptions">
        <dl className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-lg border border-border bg-surface p-4 shadow-card">
            <dt className="font-medium text-ink">Standard</dt>
            <dd className="mt-1 text-sm text-ink-2">
              Descriptions play only inside natural pauses. The video’s length does not change.
            </dd>
          </div>
          <div className="rounded-lg border border-border bg-surface p-4 shadow-card">
            <dt className="font-medium text-ink">Extended</dt>
            <dd className="mt-1 text-sm text-ink-2">
              When an essential visual has no pause long enough, the video briefly pauses. Every added pause has a
              recorded reason and counts against a fixed budget.
            </dd>
          </div>
        </dl>
      </Section>

      <Section id="limits" title="Limits">
        <ul className="max-w-3xl list-disc space-y-2 pl-5 text-ink-2 marker:text-muted">
          {limits.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </Section>
    </Container>
  );
}

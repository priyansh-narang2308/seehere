import { ArrowRight, AudioLines, FileSearch, MessageSquareQuote, ShieldCheck, Upload } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Container } from "@/components/layout/page";
import { countBuilt, pipelineStages } from "@/lib/pipeline";

const pillars = [
  {
    icon: MessageSquareQuote,
    title: "Finds what isn't said",
    body: "When a lecturer says “notice this line here”, SeeHere works out which line, and what the slide shows that the narration skips.",
  },
  {
    icon: FileSearch,
    title: "Every line has evidence",
    body: "Each description links to the frame, screen region, on-screen text and transcript it came from, so it can be checked.",
  },
  {
    icon: AudioLines,
    title: "Speaks in the pauses",
    body: "Descriptions are scheduled into natural gaps in speech, and their real spoken length is measured before they are placed.",
  },
  {
    icon: ShieldCheck,
    title: "A person approves it",
    body: "Uncertain or unverifiable descriptions are flagged. An instructor reviews everything before it is published.",
  },
];

export default function Home() {
  const built = countBuilt();
  return (
    <>
      <section className="border-b border-border">
        <Container className="py-16 sm:py-24">
          <Badge tone="warning">Research prototype · HackGlobal 2026</Badge>
          <h1 className="mt-6 max-w-3xl text-4xl font-bold tracking-tight text-balance text-ink sm:text-5xl">
            Hear what the lecture shows, not just what it says.
          </h1>
          <p className="mt-5 max-w-2xl text-lg text-ink-2">
            SeeHere creates audio descriptions for lecture videos, so blind and low-vision students can follow
            the charts, slides and “this one here” moments that narration leaves out.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button asChild size="lg">
              <Link href="/upload">
                <Upload aria-hidden="true" /> Upload a lecture
              </Link>
            </Button>
            <Button asChild size="lg" variant="secondary">
              <Link href="/methodology">
                How it works <ArrowRight aria-hidden="true" />
              </Link>
            </Button>
          </div>
        </Container>
      </section>

      <Container className="py-16">
        <h2 className="text-xl font-semibold tracking-tight text-ink">What SeeHere is designed to do</h2>
        <ul className="mt-6 grid gap-4 sm:grid-cols-2">
          {pillars.map(({ icon: Icon, title, body }) => (
            <li key={title} className="rounded-lg border border-border bg-surface p-5 shadow-card">
              <Icon aria-hidden="true" className="size-5 text-accent-strong" />
              <h3 className="mt-3 font-semibold text-ink">{title}</h3>
              <p className="mt-1.5 text-sm text-ink-2">{body}</p>
            </li>
          ))}
        </ul>
        <p className="mt-8 rounded-lg border border-warning-line bg-warning-soft px-4 py-3 text-sm text-warning">
          Research prototype: all {built} of {pipelineStages.length} pipeline stages run, and every description is
          checked against the on-screen text. That is not full fact-checking or a WCAG certification, so an
          instructor should review descriptions before publishing.{" "}
          <Link href="/methodology" className="font-medium underline underline-offset-4">
            How it works and its limits
          </Link>
          .
        </p>
      </Container>
    </>
  );
}

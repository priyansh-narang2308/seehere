"use client";

import { ArrowRight, Upload } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
  Eyebrow,
} from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Checkbox, Field, Input, Textarea } from "@/components/ui/field";
import { Kbd, Progress } from "@/components/ui/misc";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import {
  VERIFICATION_STATES,
  VerificationBadge,
  type VerificationState,
} from "@/components/ui/verification-badge";

export function InteractiveShowcase() {
  const { toast } = useToast();
  const [title, setTitle] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const titleError =
    submitted && title.trim() === "" ? "Enter a lecture title." : undefined;

  return (
    <>
      <section aria-labelledby="buttons" className="mt-12">
        <Eyebrow as="h2" id="buttons">
          Buttons
        </Eyebrow>
        <div className="mt-4 flex flex-wrap items-center gap-3 rounded-lg border border-border bg-surface p-5 shadow-card">
          <Button>
            <Upload aria-hidden="true" /> Upload lecture
          </Button>
          <Button variant="secondary">Review cues</Button>
          <Button variant="ghost">Cancel</Button>
          <Button variant="danger">Reject cue</Button>
          <Button variant="link">
            View evidence <ArrowRight aria-hidden="true" />
          </Button>
          <Button loading>Processing</Button>
          <Button disabled>Disabled</Button>
          <Button size="sm" variant="secondary">
            Small
          </Button>
          <Button size="lg">Large</Button>
        </div>
      </section>

      <section aria-labelledby="badges" className="mt-12">
        <Eyebrow as="h2" id="badges">
          Status and verification
        </Eyebrow>
        <div className="mt-4 rounded-lg border border-border bg-surface p-5 shadow-card">
          <div className="flex flex-wrap gap-2">
            {(Object.keys(VERIFICATION_STATES) as VerificationState[]).map(
              (s) => (
                <VerificationBadge key={s} state={s} />
              ),
            )}
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Badge>Draft</Badge>
            <Badge tone="accent">Cue 12 of 31</Badge>
            <Badge tone="warning">Awaiting instructor review</Badge>
            <Badge shape="tag" tone="accent">
              02:14
            </Badge>
          </div>
          <dl className="mt-5 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
            {(
              Object.entries(VERIFICATION_STATES) as [
                VerificationState,
                (typeof VERIFICATION_STATES)[VerificationState],
              ][]
            ).map(([key, v]) => (
              <div key={key}>
                <dt className="font-medium text-ink">{v.label}</dt>
                <dd className="text-muted">{v.help}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <section aria-labelledby="forms" className="mt-12">
        <Eyebrow as="h2" id="forms">
          Forms
        </Eyebrow>
        <form
          noValidate
          className="mt-4 grid gap-5 rounded-lg border border-border bg-surface p-5 shadow-card sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            setSubmitted(true);
            if (title.trim())
              toast({
                title: "Saved",
                description: `“${title}” is ready.`,
                tone: "success",
              });
          }}
        >
          <Field
            label="Lecture title"
            required
            error={titleError}
            hint="Shown to students in the player."
          >
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Intro to Data Analysis, Lecture 7"
            />
          </Field>
          <Field label="Instructor note" hint="Optional context for reviewers.">
            <Textarea placeholder="The chart on slide 4 is the key result." />
          </Field>
          <Checkbox
            className="sm:col-span-2"
            label="I own this video or have permission to process it."
          />
          <div className="sm:col-span-2">
            <Button type="submit">Save details</Button>
          </div>
        </form>
      </section>

      <section
        aria-labelledby="composition"
        className="mt-12 grid gap-6 lg:grid-cols-2"
      >
        <div>
          <Eyebrow as="h2" id="composition">
            Card composition
          </Eyebrow>
          <Card className="mt-4">
            <CardHeader>
              <div className="flex items-center justify-between gap-3">
                <CardTitle>Audio description</CardTitle>
                <VerificationBadge state="verified_text_match" />
              </div>
              <CardDescription>Cue 12 · source frame 02:14</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-[15px] leading-relaxed font-medium text-ink">
                “The blue line rises to{" "}
                <span className="text-accent-strong">42</span> at Week 3, then
                falls to <span className="text-accent-strong">31</span> at Week
                4.”
              </p>
              <p className="mt-2 font-mono text-xs text-muted">
                Sample content · 2.6 s · fits a 3.1 s pause
              </p>
            </CardContent>
            <CardFooter>
              <Button size="sm">Approve</Button>
              <Button size="sm" variant="secondary">
                Edit
              </Button>
              <Button size="sm" variant="ghost" className="ml-auto">
                Evidence
              </Button>
            </CardFooter>
          </Card>
        </div>

        <div>
          <Eyebrow as="h2" id="tabs-label">
            Tabs, progress, dialog, toast
          </Eyebrow>
          <div className="mt-4 rounded-lg border border-border bg-surface p-5 shadow-card">
            <Tabs defaultValue="standard">
              <TabsList aria-label="Description mode">
                <TabsTrigger value="standard">Standard</TabsTrigger>
                <TabsTrigger value="extended">Extended</TabsTrigger>
              </TabsList>
              <TabsContent value="standard" className="text-sm text-ink-2">
                Descriptions play only inside natural pauses. Playback length is
                unchanged.
              </TabsContent>
              <TabsContent value="extended" className="text-sm text-ink-2">
                Short, budgeted pauses are added when essential visuals have no
                gap. Each pause has a reason.
              </TabsContent>
            </Tabs>

            <div className="mt-6 space-y-2">
              <div className="flex justify-between text-sm">
                <span className="font-medium text-ink">
                  Transcribing speech
                </span>
                <span className="font-mono text-muted">64%</span>
              </div>
              <Progress label="Transcribing speech" value={64} />
            </div>

            <div className="mt-6 flex flex-wrap items-center gap-3">
              <Dialog>
                <DialogTrigger asChild>
                  <Button variant="secondary">Open dialog</Button>
                </DialogTrigger>
                <DialogContent
                  title="Reject this description?"
                  description="The cue will be removed from the schedule. You can restore it from the review history."
                >
                  <DialogFooter>
                    <DialogClose asChild>
                      <Button variant="ghost">Keep cue</Button>
                    </DialogClose>
                    <DialogClose asChild>
                      <Button
                        variant="danger"
                        onClick={() =>
                          toast({ title: "Cue rejected", tone: "info" })
                        }
                      >
                        Reject cue
                      </Button>
                    </DialogClose>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
              <Button
                variant="secondary"
                onClick={() =>
                  toast({
                    title: "Export failed",
                    description: "Retry in a moment.",
                    tone: "error",
                  })
                }
              >
                Show error toast
              </Button>
              <span className="text-sm text-muted">
                Close with <Kbd>Esc</Kbd>
              </span>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}

"use client";

import { AudioLines, Images, RotateCcw, TriangleAlert, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/misc";
import {
  ApiError,
  formatBytes,
  formatDuration,
  frameImageUrl,
  getJson,
  jobAction,
  type Job,
  type JobList,
  type JobStatus,
  type PreparedMedia,
  type Transcript,
} from "@/lib/api";
import { TranscriptView } from "./transcript-view";

const POLL_MS = 1000;
/** After this long in the queue with no attempt yet, say that no worker seems to be running. */
const WAITING_HINT_S = 15;

const STATUS: Record<JobStatus, { label: string; tone: "neutral" | "accent" | "success" | "warning" | "danger" }> = {
  queued: { label: "Waiting", tone: "neutral" },
  running: { label: "Running", tone: "accent" },
  succeeded: { label: "Done", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
  cancelled: { label: "Cancelled", tone: "warning" },
};

const STAGES: Record<string, string> = {
  inspect: "Checking the video",
  audio: "Extracting the audio track",
  frames: "Sampling frames",
  save: "Saving results",
  model: "Loading the speech model",
  transcribe: "Recognizing speech",
};

const isActive = (j: Job) => j.status === "queued" || j.status === "running";
const seconds = (a: string, b: string) => (new Date(a).getTime() - new Date(b).getTime()) / 1000;
const timeFormat = new Intl.DateTimeFormat("en-GB", { timeStyle: "medium" });

export function JobPanel({ projectId }: { projectId: string }) {
  const [list, setList] = useState<JobList | null>(null);
  const [media, setMedia] = useState<PreparedMedia | null>(null);
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const transcriptLoadedFor = useRef<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const mediaLoadedFor = useRef<string | null>(null);
  const wasActive = useRef(false);
  const router = useRouter();
  // Polling must not restart when the router object changes, so read it through a ref.
  const routerRef = useRef(router);
  useEffect(() => {
    routerRef.current = router;
  }, [router]);

  const refresh = useCallback(() => setTick((n) => n + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    getJson<JobList>(`/api/projects/${projectId}/jobs`, { signal: controller.signal })
      .then((next) => {
        setList(next);
        setError(null);
        const prepared = next.jobs.find((j) => j.kind === "media.prepare" && j.status === "succeeded");
        const key = prepared ? `${prepared.id}:${prepared.finished_at}` : null;
        if (key && mediaLoadedFor.current !== key) {
          mediaLoadedFor.current = key;
          getJson<PreparedMedia>(`/api/projects/${projectId}/media`, { signal: controller.signal })
            .then(setMedia)
            .catch(() => {});
        }
        if (!prepared) {
          mediaLoadedFor.current = null;
          setMedia(null);
        }
        const speech = next.jobs.find((j) => j.kind === "speech.transcribe" && j.status === "succeeded");
        const speechKey = speech ? `${speech.id}:${speech.finished_at}` : null;
        if (speechKey && transcriptLoadedFor.current !== speechKey) {
          transcriptLoadedFor.current = speechKey;
          getJson<Transcript>(`/api/projects/${projectId}/transcript`, { signal: controller.signal })
            .then((t) => setTranscript(t.available ? t : null))
            .catch(() => {});
        }
        if (!speech) {
          transcriptLoadedFor.current = null;
          setTranscript(null);
        }
        const active = next.jobs.some(isActive);
        if (active) timer = setTimeout(refresh, POLL_MS);
        // Work just finished: re-render the server parts of the page (project status badge).
        else if (wasActive.current) routerRef.current.refresh();
        wasActive.current = active;
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setError(e instanceof ApiError ? e.message : "Could not load progress.");
        timer = setTimeout(refresh, POLL_MS * 5);
      });
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [projectId, tick, refresh]);

  async function act(job: Job, action: "cancel" | "retry") {
    setBusy(job.id);
    try {
      await jobAction(job.id, action);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The action failed.");
    } finally {
      setBusy(null);
      refresh();
    }
  }

  if (!list) {
    return error ? (
      <p role="alert" className="rounded-lg border border-danger-line bg-danger-soft px-4 py-3 text-sm text-danger">
        {error}
      </p>
    ) : (
      <p role="status" className="text-sm text-muted">
        Loading progress…
      </p>
    );
  }

  return (
    <section aria-labelledby="jobs-heading" className="rounded-lg border border-border bg-surface shadow-card">
      <h2 id="jobs-heading" className="border-b border-border px-5 py-4 font-semibold text-ink">
        Analysis
      </h2>
      {/* Announce status changes only, not every progress update. */}
      <p role="status" aria-live="polite" className="sr-only">
        {list.jobs.map((j) => `${j.label}: ${STATUS[j.status].label}.`).join(" ")}
      </p>
      {error && (
        <p role="alert" className="mx-5 mt-4 rounded-md border border-danger-line bg-danger-soft px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}
      {list.jobs.length === 0 ? (
        <p className="px-5 py-4 text-sm text-muted">No analysis has been queued for this project.</p>
      ) : (
        <ul className="divide-y divide-border">
          {list.jobs.map((job) => (
            <JobRow key={job.id} job={job} now={list.now} busy={busy === job.id} onAction={act} />
          ))}
        </ul>
      )}
      {media && <PreparedOutputs media={media} />}
      {transcript && <TranscriptView transcript={transcript} />}
    </section>
  );
}

function JobRow({
  job,
  now,
  busy,
  onAction,
}: {
  job: Job;
  now: string;
  busy: boolean;
  onAction: (job: Job, action: "cancel" | "retry") => void;
}) {
  const status = STATUS[job.status];
  const stage = job.stage ? (STAGES[job.stage] ?? job.stage) : null;
  const retrying = job.status === "queued" && job.attempts > 0 && job.error;
  const waitingLong = job.status === "queued" && job.attempts === 0 && seconds(now, job.created_at) > WAITING_HINT_S;

  return (
    <li className="space-y-3 px-5 py-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h3 className="font-medium text-ink">{job.label}</h3>
          <Badge tone={status.tone}>{status.label}</Badge>
        </div>
        <div className="flex gap-2">
          {isActive(job) && !job.cancel_requested && (
            <Button size="sm" variant="secondary" loading={busy} onClick={() => onAction(job, "cancel")}>
              <X aria-hidden="true" /> Cancel
            </Button>
          )}
          {(job.status === "failed" || job.status === "cancelled") && (
            <Button size="sm" variant="secondary" loading={busy} onClick={() => onAction(job, "retry")}>
              <RotateCcw aria-hidden="true" /> {job.status === "failed" ? "Try again" : "Run again"}
            </Button>
          )}
        </div>
      </div>

      {job.status === "running" && (
        <div className="space-y-1.5">
          <div className="flex justify-between text-sm">
            <span className="text-ink-2">{job.cancel_requested ? "Stopping…" : (stage ?? "Starting")}</span>
            <span className="font-mono text-muted">{Math.round(job.progress * 100)}%</span>
          </div>
          <Progress label={`${job.label} progress`} value={job.progress * 100} />
          {job.attempts > 1 && (
            <p className="text-xs text-muted">
              Attempt {job.attempts} of {job.max_attempts}
            </p>
          )}
        </div>
      )}

      {retrying && (
        <p className="text-sm text-warning">
          Attempt {job.attempts} of {job.max_attempts} stopped: {job.error} It will be retried at{" "}
          <time dateTime={job.run_after}>{timeFormat.format(new Date(job.run_after))}</time>.
        </p>
      )}
      {job.status === "queued" && !retrying && (
        <p className="text-sm text-muted">
          {waitingLong
            ? "Still waiting for a worker to pick this up. If it does not start, the background worker may not be running."
            : "Waiting to start…"}
        </p>
      )}
      {job.status === "failed" && job.error && (
        <p className="flex gap-2 text-sm text-danger">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          <span>
            {job.error}
            {job.attempts > 1 && ` (after ${job.attempts} attempts)`}
          </span>
        </p>
      )}
    </li>
  );
}

function PreparedOutputs({ media }: { media: PreparedMedia }) {
  const { audio, frames } = media;
  const every = frames.fps ? (frames.fps === 1 ? "one per second" : `${frames.fps} per second`) : null;
  return (
    <div className="space-y-4 border-t border-border px-5 py-4">
      <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
        <div>
          <dt className="flex items-center gap-1.5 text-muted">
            <AudioLines aria-hidden="true" className="size-4" /> Speech audio
          </dt>
          <dd className="mt-0.5 font-medium text-ink">
            {audio
              ? `${audio.sample_rate / 1000} kHz ${audio.channels === 1 ? "mono" : `${audio.channels} channels`}, ${
                  audio.duration_s != null ? formatDuration(audio.duration_s) : "unknown length"
                } (${formatBytes(audio.size_bytes)})`
              : "Not available"}
          </dd>
        </div>
        <div>
          <dt className="flex items-center gap-1.5 text-muted">
            <Images aria-hidden="true" className="size-4" /> Sampled frames
          </dt>
          <dd className="mt-0.5 font-medium text-ink">
            {frames.count} {frames.count === 1 ? "frame" : "frames"}
            {every && `, ${every}`}
            {frames.first_s != null && frames.last_s != null &&
              ` (${formatDuration(frames.first_s)} to ${formatDuration(frames.last_s)})`}
          </dd>
        </div>
      </dl>
      {frames.preview.length > 0 && (
        <ul aria-label="Frame preview" className="grid grid-cols-3 gap-2 sm:grid-cols-6">
          {frames.preview.map((f) => (
            <li key={f.id}>
              <figure>
                {/* Served by the API from private storage; next/image optimization is not used. */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={frameImageUrl(f.id)}
                  alt={`Video frame at ${formatDuration(f.t_s)}`}
                  loading="lazy"
                  className="aspect-video w-full rounded-sm border border-border bg-sunken object-cover"
                />
                <figcaption className="mt-1 font-mono text-xs text-muted">{formatDuration(f.t_s)}</figcaption>
              </figure>
            </li>
          ))}
        </ul>
      )}
      <p className="text-xs text-muted">
        These are the inputs for visual analysis, which is not built yet.
      </p>
    </div>
  );
}

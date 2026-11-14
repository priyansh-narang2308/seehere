import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Job, JobList, PreparedMedia, Transcript } from "@/lib/api";
import { JobPanel } from "./job-panel";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));

const PROJECT = "0b8f7c1e-1d2a-4c3b-9e8f-7a6b5c4d3e2f";
const NOW = "2026-11-14T10:00:30Z";

const job = (over: Partial<Job> = {}): Job => ({
  id: "job-1",
  kind: "media.prepare",
  label: "Media preparation",
  status: "queued",
  stage: null,
  progress: 0,
  attempts: 0,
  max_attempts: 3,
  cancel_requested: false,
  error: null,
  created_at: "2026-11-14T10:00:25Z",
  run_after: "2026-11-14T10:00:25Z",
  finished_at: null,
  ...over,
});

const media: PreparedMedia = {
  audio: { duration_s: 8, sample_rate: 16000, channels: 1, size_bytes: 256_044 },
  frames: {
    count: 8,
    fps: 1,
    first_s: 0,
    last_s: 7,
    preview: [
      { id: "f0", t_s: 0 },
      { id: "f7", t_s: 7 },
    ],
  },
};

const transcript: Transcript = {
  available: true,
  provider: "faster-whisper:small.en",
  language: "en",
  duration_s: 8,
  word_count: 6,
  segments: [
    { start_s: 0, end_s: 2.4, text: "Look at the bar chart.", words: [] },
    { start_s: 4.85, end_s: 7.75, text: "Sales doubled.", words: [] },
  ],
};

type Route = (url: string, init?: RequestInit) => unknown;

/** fetch double that answers by URL; each call to `jobs` can return the next queued state. */
function stubApi(jobs: Job[][], extra: Route = () => undefined) {
  let i = 0;
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    const special = extra(url, init);
    if (special !== undefined) return Response.json(special);
    if (url.endsWith(`/api/projects/${PROJECT}/jobs`)) {
      const list: JobList = { now: NOW, jobs: jobs[Math.min(i++, jobs.length - 1)] };
      return Response.json(list);
    }
    if (url.endsWith(`/api/projects/${PROJECT}/media`)) return Response.json(media);
    if (url.endsWith(`/api/projects/${PROJECT}/transcript`)) return Response.json(transcript);
    throw new Error(`unexpected ${url}`);
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  refresh.mockReset();
});

describe("JobPanel", () => {
  it("shows the stage and progress of a running job", async () => {
    stubApi([[job({ status: "running", stage: "audio", progress: 0.42, attempts: 1 })]]);
    render(<JobPanel projectId={PROJECT} />);
    expect(await screen.findByText("Extracting the audio track")).toBeInTheDocument();
    expect(screen.getByText("42%")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Media preparation progress" })).toHaveAttribute("aria-valuenow", "42");
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Media preparation: Running.");
  });

  it("polls until the job finishes, then shows the outputs and refreshes the page", async () => {
    const fetch = stubApi([
      [job({ status: "running", stage: "frames", progress: 0.6, attempts: 1 })],
      [job({ status: "succeeded", stage: "save", progress: 1, attempts: 1, finished_at: NOW })],
    ]);
    const { container } = render(<JobPanel projectId={PROJECT} />);
    expect(await screen.findByText("Sampling frames")).toBeInTheDocument();
    expect(await screen.findByText("Done", {}, { timeout: 3000 })).toBeInTheDocument();
    expect(await screen.findByText("16 kHz mono, 0:08 (250 KB)")).toBeInTheDocument();
    expect(screen.getByText("8 frames, one per second (0:00 to 0:07)")).toBeInTheDocument();
    const images = within(screen.getByRole("list", { name: "Frame preview" })).getAllByRole("img");
    expect(images.map((img) => img.getAttribute("alt"))).toEqual(["Video frame at 0:00", "Video frame at 0:07"]);
    expect(images[0]).toHaveAttribute("src", expect.stringMatching(/\/api\/frames\/f0\/image$/));
    expect(refresh).toHaveBeenCalledTimes(1);

    // Polling stops once nothing is active.
    const calls = fetch.mock.calls.length;
    await new Promise((r) => setTimeout(r, 1500));
    expect(fetch.mock.calls.length).toBe(calls);

    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });

  it("explains a failure and offers to try again", async () => {
    const posts: string[] = [];
    stubApi(
      [
        [job({ status: "failed", attempts: 1, error: "The video frames could not be decoded.", finished_at: NOW })],
        [job()],
      ],
      (url, init) => {
        if (init?.method === "POST") {
          posts.push(`${url} ${new Headers(init.headers).get("X-SeeHere-Request")}`);
          return job();
        }
      },
    );
    render(<JobPanel projectId={PROJECT} />);
    expect(await screen.findByText("The video frames could not be decoded.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(posts).toEqual([expect.stringMatching(/\/api\/jobs\/job-1\/retry 1$/)]);
    expect(await screen.findByText("Waiting to start…")).toBeInTheDocument();
  });

  it("cancels with the request header and shows Run again afterwards", async () => {
    const posts: string[] = [];
    stubApi(
      [[job()], [job({ status: "cancelled", error: "Cancelled on request.", finished_at: NOW })]],
      (url, init) => {
        if (init?.method === "POST") {
          posts.push(url);
          return job({ status: "cancelled" });
        }
      },
    );
    render(<JobPanel projectId={PROJECT} />);
    await userEvent.click(await screen.findByRole("button", { name: /cancel/i }));
    expect(posts).toEqual([expect.stringMatching(/\/api\/jobs\/job-1\/cancel$/)]);
    expect(await screen.findByRole("button", { name: /run again/i })).toBeInTheDocument();
  });

  it("says when a retry is scheduled after a failed attempt", async () => {
    stubApi([[job({ attempts: 1, error: "An unexpected error stopped this step.", run_after: "2026-11-14T10:01:00Z" })]]);
    render(<JobPanel projectId={PROJECT} />);
    expect(
      await screen.findByText(/Attempt 1 of 3 stopped: An unexpected error stopped this step\. It will be retried at/),
    ).toBeInTheDocument();
  });

  it("hints that the worker may be down when a job waits too long", async () => {
    stubApi([[job({ created_at: "2026-11-14T09:59:00Z" })]]);
    render(<JobPanel projectId={PROJECT} />);
    expect(await screen.findByText(/background worker may not be running/)).toBeInTheDocument();
  });

  it("reports an unreachable API", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("down"))));
    render(<JobPanel projectId={PROJECT} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("The SeeHere API could not be reached.");
  });

  it("does not offer actions while a cancel is pending", async () => {
    stubApi([[job({ status: "running", cancel_requested: true, attempts: 1, stage: "frames", progress: 0.5 })]]);
    render(<JobPanel projectId={PROJECT} />);
    expect(await screen.findByText("Stopping…")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
    await waitFor(() => expect(refresh).not.toHaveBeenCalled());
  });

  it("shows the timed transcript once speech-to-text is done", async () => {
    const speech = job({ id: "job-2", kind: "speech.transcribe", label: "Speech-to-text", status: "succeeded", progress: 1, finished_at: NOW });
    stubApi([[job({ status: "succeeded", progress: 1, finished_at: NOW }), speech]]);
    const { container } = render(<JobPanel projectId={PROJECT} />);
    expect(await screen.findByText(/6 words with timings, English, recognized locally by Whisper small\.en/)).toBeInTheDocument();
    const rows = within(screen.getByRole("list", { name: "Transcript segments" })).getAllByRole("listitem");
    expect(rows.map((r) => r.textContent)).toEqual(["0:00Look at the bar chart.", "0:05Sales doubled."]);
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });

  it("labels the speech stages while recognizing", async () => {
    stubApi([[job({ kind: "speech.transcribe", label: "Speech-to-text", status: "running", stage: "transcribe", progress: 0.5, attempts: 1 })]]);
    render(<JobPanel projectId={PROJECT} />);
    expect(await screen.findByText("Recognizing speech")).toBeInTheDocument();
  });
});

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Cue, CueLedger, Deck, Job, JobList, PreparedMedia, References, Schedule, Transcript, Visuals } from "@/lib/api";
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
  scenes: null,
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

const noDeck: Deck = { available: false, filename: null, kind: null, ingested: false, pages: [] };

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
    if (url.endsWith(`/api/projects/${PROJECT}/deck`)) return Response.json(noDeck);
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
    expect(screen.queryByRole("button", { name: /cancel|try again|run again/i })).toBeNull();
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

  it("shows keyframes once scene detection is done", async () => {
    const withScenes: PreparedMedia = {
      ...media,
      scenes: { keyframes: [{ id: "k0", t_s: 0, scene_index: 0 }, { id: "k6", t_s: 6, scene_index: 1 }], revisits: 1 },
    };
    stubApi([[job({ status: "succeeded", progress: 1, finished_at: NOW })]], (url) =>
      url.endsWith("/media") ? withScenes : undefined,
    );
    render(<JobPanel projectId={PROJECT} />);
    expect(await screen.findByText(/found where the picture changes, plus 1 return to an earlier slide\./)).toBeInTheDocument();
    const images = within(screen.getByRole("list", { name: "Keyframes" })).getAllByRole("img");
    expect(images.map((i) => i.getAttribute("alt"))).toEqual(["Keyframe at 0:00", "Keyframe at 0:06"]);
  });

  it("shows on-screen text by keyframe and marks low-confidence lines", async () => {
    const read = job({ id: "job-4", kind: "ocr.extract", label: "On-screen text", status: "succeeded", progress: 1, finished_at: NOW });
    const box = { x: 0.06, y: 0.08, w: 0.5, h: 0.1 };
    stubApi([[job({ status: "succeeded", progress: 1, finished_at: NOW }), read]], (url) =>
      url.endsWith("/ocr")
        ? {
            available: true,
            keyframes: [
              { frame_id: "k0", t_s: 0, regions: [{ text: "Quarterly Revenue", confidence: 0.95, ...box }, { text: "Rev 12.5%", confidence: 0.41, ...box }] },
              { frame_id: "k6", t_s: 6, regions: [] },
            ],
          }
        : undefined,
    );
    const { container } = render(<JobPanel projectId={PROJECT} />);
    expect(await screen.findByText(/Read by OCR from 1 of 2 keyframes/)).toBeInTheDocument();
    const list = within(screen.getByRole("list", { name: "Text by keyframe" }));
    expect(list.getByText("Quarterly Revenue")).toBeInTheDocument();
    expect(list.getByText("Rev 12.5%")).toHaveTextContent("Rev 12.5%(low confidence)");
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });

  it("lists visual content by priority with what was not said aloud", async () => {
    const analyzed = job({ id: "job-5", kind: "visual.analyze", label: "Visual analysis", status: "succeeded", progress: 1, finished_at: NOW });
    const scored = job({ id: "job-6", kind: "coverage.score", label: "Seen versus said", status: "succeeded", progress: 1, finished_at: NOW });
    const unit = {
      frame_id: "k0",
      lines: [],
      details: "",
      x: 0.06,
      y: 0.3,
      w: 0.5,
      h: 0.06,
      t_start_s: 0,
      t_end_s: 5,
      source: "ocr",
    };
    const visuals: Visuals = {
      available: true,
      scored: true,
      units: [
        { ...unit, id: "u1", kind: "text_block", label: "Operating margin 41.7% in 2022", coverage: 0, priority: 0.6, said: [], unsaid: ["margin", "41.7%"] },
        { ...unit, id: "u2", kind: "chart", label: "Revenue rose 12.5%", coverage: 0.75, priority: 0.25, said: ["revenue"], unsaid: [] },
      ],
    };
    stubApi([[job({ status: "succeeded", progress: 1, finished_at: NOW }), analyzed, scored]], (url) =>
      url.endsWith("/visuals") ? visuals : undefined,
    );
    const { container } = render(<JobPanel projectId={PROJECT} />);
    const list = within(await screen.findByRole("list", { name: "Visual content by priority" }));
    const items = list.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Operating margin 41.7% in 2022");
    expect(items[0]).toHaveTextContent("0% said aloud · not said: margin, 41.7%");
    expect(items[1]).toHaveTextContent("Chart");
    expect(items[1]).toHaveTextContent("75% said aloud");
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });

  it("lists references and descriptions, and shows a cue's evidence on request", async () => {
    const written = job({ id: "job-8", kind: "descriptions.generate", label: "Descriptions", status: "succeeded", progress: 1, finished_at: NOW });
    const cue: Cue = {
      id: "c1",
      visual_unit_id: "u1",
      text_short: "On screen: “Operating margin 41.7% in 2022”.",
      text_medium: null,
      text_long: null,
      anchor_t_s: 3.2,
      priority: 0.8,
      verification_state: "needs_review",
      review_status: "pending",
    };
    const references: References = {
      available: true,
      references: [
        { phrase: "this number here", t_s: 3.2, status: "linked", confidence: 0.9, visual_unit_id: "u1", label: "Operating margin 41.7% in 2022" },
        { phrase: "this line", t_s: 7, status: "ambiguous", confidence: 0, visual_unit_id: null, label: null },
      ],
    };
    const ledger: CueLedger = {
      cue,
      evidence: [
        { kind: "frame", note: "keyframe", frame: { id: "k0", t_s: 0, image_url: "/api/frames/k0/image" }, ocr_region: null, slide: null, visual_unit: null, transcript: null },
        { kind: "ocr_region", note: "text read", frame: null, ocr_region: { text: "Operating margin 41.7% in 2022", confidence: 0.93, box: { x: 0.06, y: 0.46, w: 0.5, h: 0.06 } }, slide: null, visual_unit: null, transcript: null },
        { kind: "transcript_span", note: "spoken reference: this number here", frame: null, ocr_region: null, slide: null, visual_unit: null, transcript: { start_s: 3.2, end_s: 3.9, text: "this number here" } },
        { kind: "visual_unit", note: "ocr unit", frame: null, ocr_region: null, slide: null, visual_unit: { kind: "text_block", label: "Operating margin 41.7% in 2022", box: { x: 0.06, y: 0.46, w: 0.5, h: 0.06 }, t_start_s: 0, t_end_s: 5, coverage: 0.25 }, transcript: null },
      ],
      checks: [
        { claim: "41.7%", check: "number_match", result: "pass", resulting_state: "verified_text_match", detail: { source: "ocr", ocr_confidence: 0.93 } },
        { claim: "2023", check: "number_match", result: "fail", resulting_state: "needs_review", detail: { reason: "this value does not appear on screen or on the deck page" } },
      ],
      decisions: [],
    };
    stubApi([[job({ status: "succeeded", progress: 1, finished_at: NOW }), written]], (url) =>
      url.endsWith("/cues") ? { available: true, cues: [cue] } : url.endsWith("/references") ? references : url.endsWith("/c1/evidence") ? ledger : undefined,
    );
    const { container } = render(<JobPanel projectId={PROJECT} />);
    const refs = within(await screen.findByRole("list", { name: "Spoken references" })).getAllByRole("listitem");
    expect(refs[0]).toHaveTextContent("“this number here” points at “Operating margin 41.7% in 2022” (90% confidence)");
    expect(refs[1]).toHaveTextContent("needs review: more than one item fits");

    const cues = within(screen.getByRole("list", { name: "Descriptions" }));
    expect(cues.getByText(cue.text_short)).toBeInTheDocument();
    expect(cues.getByText("Needs human review")).toBeInTheDocument();
    const button = cues.getByRole("button", { name: "Show evidence" });
    await userEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    const evidence = within(await screen.findByRole("list", { name: "Evidence" }));
    expect(evidence.getByText(/Read on screen: “Operating margin 41.7% in 2022” \(93% OCR confidence\)/)).toBeInTheDocument();
    expect(evidence.getByText(/Pointed at \(0:03\)/)).toHaveTextContent("“this number here”");
    expect(screen.getByRole("img", { name: "Keyframe at 0:00" })).toHaveAttribute("src", "/api/frames/k0/image");
    const checks = within(screen.getByRole("list", { name: "Checks" })).getAllByRole("listitem");
    expect(checks[0]).toHaveTextContent("Found number “41.7%” (read on screen) → Verified text match");
    expect(screen.getByTestId("unit-box")).toHaveStyle({ left: "6%", width: "50%" });
    expect(screen.getAllByTestId("ocr-box")).toHaveLength(1);
    expect(checks[1]).toHaveTextContent("Not found number “2023”: this value does not appear on screen or on the deck page");
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });

  it("shows the schedule: what plays in which pause, the solver comparison and extended pauses", async () => {
    const planned = job({ id: "job-10", kind: "schedule.plan", label: "Scheduling", status: "succeeded", progress: 1, finished_at: NOW });
    const voiced = job({ id: "job-11", kind: "speech.synthesize", label: "Speech synthesis", status: "succeeded", progress: 1, finished_at: NOW });
    const placed = { cue_id: "c4", variant: "short" as const, text: "On screen: “Next steps”.", start_s: 6.05, end_s: 7.89, verification_state: "verified_text_match" as const, pause_s: 0, pause_reason: null, audio_url: "/api/audio/a4", audio_s: 1.62 };
    const base = { available: true, status: "succeeded" as const, windows: [{ start_s: 6.05, end_s: 12 }], priority_placed_share: 0.5, duration_ms: 0.4, pause_budget_s: null, paused_s: null, extended_duration_s: null, comparison: null };
    const standard: Schedule = {
      ...base,
      solver: "cp_sat",
      mode: "standard",
      placements: [placed],
      not_placed: [{ cue_id: "c1", text: "On screen: “Quarterly Revenue”.", reason: "no pause in speech while it is on screen" }],
      comparison: {
        greedy: { placed: 1, priority_placed_share: 0.4, described_s: 1.8, duration_ms: 0.1 },
        cp_sat: { placed: 1, priority_placed_share: 0.5, described_s: 1.8, duration_ms: 4, status: "optimal" },
      },
    };
    const extended: Schedule = {
      ...base,
      solver: "cp_sat",
      mode: "extended",
      placements: [
        { ...placed, cue_id: "c1", text: "On screen: “Quarterly Revenue”.", start_s: 0, end_s: 1.9, pause_s: 1.4, pause_reason: "Quarterly Revenue is on screen while the speaker talks.", audio_url: "/api/audio/a1", audio_s: 1.9 },
        placed,
      ],
      not_placed: [],
      pause_budget_s: 1.92,
      paused_s: 1.4,
    };
    stubApi([[job({ status: "succeeded", progress: 1, finished_at: NOW }), planned, voiced]], (url) =>
      url.endsWith("/schedule") ? standard : url.endsWith("/schedule?mode=extended") ? extended : undefined,
    );
    const { container } = render(<JobPanel projectId={PROJECT} />);
    expect(await screen.findByText(/1 of 2 descriptions fit into pauses in speech, with no overlap\. Lengths are measured/)).toBeInTheDocument();
    expect(screen.getByText(/greedy placed 1 \(\s*40% of priority\) and CP-SAT placed 1 \(50%\)/)).toBeInTheDocument();
    const item = within(screen.getByRole("list", { name: "Scheduled descriptions" })).getByRole("listitem");
    expect(item).toHaveTextContent("0:06.0–0:07.8On screen: “Next steps”. (short, 1.6 s spoken)");
    expect(within(item).getByLabelText("Play: On screen: “Next steps”.")).toHaveAttribute("src", "/api/audio/a4");
    expect(within(screen.getByRole("list", { name: "Descriptions not voiced" })).getByRole("listitem")).toHaveTextContent(
      "On screen: “Quarterly Revenue”. — no pause in speech while it is on screen",
    );
    let results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);

    await userEvent.click(screen.getByRole("button", { name: "extended" }));
    expect(screen.getByRole("button", { name: "extended" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText(/2 of 2 descriptions are voiced; the video pauses 1\.4 s in total \(budget 1\.92 s\)/)).toBeInTheDocument();
    expect(screen.getByText(/Video pauses 1\.4 s: Quarterly Revenue is on screen while the speaker talks\./)).toBeInTheDocument();
    results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });

  it("uploads a deck with the request header and lists matched pages", async () => {
    const posts: string[] = [];
    const deck: Deck = {
      available: true,
      filename: "lecture.pptx",
      kind: "pptx",
      ingested: true,
      pages: [
        { page: 1, text: "Quarterly Revenue\nRevenue rose", frame_id: "k0", t_s: 0, score: 0.95 },
        { page: 2, text: "Appendix", frame_id: null, t_s: null, score: 0.1 },
      ],
    };
    stubApi([[job({ status: "succeeded", progress: 1, finished_at: NOW })]], (url, init) => {
      if (url.endsWith("/deck") && init?.method === "POST") {
        const h = new Headers(init.headers);
        posts.push(`${h.get("X-SeeHere-Request")} ${h.get("X-SeeHere-Filename")}`);
        return deck;
      }
    });
    const { container } = render(<JobPanel projectId={PROJECT} />);
    await userEvent.upload(await screen.findByLabelText("Slide deck file"), new File(["x"], "lecture.pptx"));
    expect(posts).toEqual(["1 lecture.pptx"]);
    expect(await screen.findByText(/2 pages, 1 matched to the video\./)).toBeInTheDocument();
    const rows = within(screen.getByRole("list", { name: "Deck pages" })).getAllByRole("listitem");
    expect(rows.map((r) => r.textContent)).toEqual(["Page 1at 0:00Quarterly Revenue", "Page 2Not matchedAppendix"]);
    expect(screen.getByRole("button", { name: /replace deck/i })).toBeInTheDocument();
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });

  it("shows why a deck was refused", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith("/jobs")) return Response.json({ now: NOW, jobs: [] });
      if (url.endsWith("/deck") && init?.method === "POST")
        return Response.json({ error: { code: "unsupported_deck", message: "This file is not a supported slide deck." } }, { status: 415 });
      return Response.json(noDeck);
    }));
    render(<JobPanel projectId={PROJECT} />);
    await userEvent.upload(await screen.findByLabelText("Slide deck file"), new File(["x"], "notes.pptx"));
    expect(await screen.findByRole("alert")).toHaveTextContent("This file is not a supported slide deck.");
  });
});

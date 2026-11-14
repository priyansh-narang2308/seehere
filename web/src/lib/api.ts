/** Typed client for the SeeHere API. Mirrors backend/src/seehere/api/projects.py. */

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

/** Server components may reach the API on an internal address (e.g. inside Docker). */
export const SERVER_API_BASE = process.env.API_INTERNAL_URL ?? API_BASE;

export type ProjectStatus = "uploaded" | "processing" | "ready" | "failed";

export type MediaSummary = {
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  duration_s: number | null;
  width: number | null;
  height: number | null;
  video_codec: string | null;
  audio_codec: string | null;
};

export type Project = {
  id: string;
  title: string;
  status: ProjectStatus;
  created_at: string;
  expires_at: string | null;
  source: MediaSummary | null;
};

export type UploadConfig = {
  max_upload_bytes: number;
  max_video_duration_s: number;
  accept: string;
  formats: string[];
  retention_hours: number;
};

export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export type Job = {
  id: string;
  kind: string;
  label: string;
  status: JobStatus;
  stage: string | null;
  progress: number;
  attempts: number;
  max_attempts: number;
  cancel_requested: boolean;
  error: string | null;
  created_at: string;
  run_after: string;
  finished_at: string | null;
};

/** `now` is the server's clock, for timing comparisons that do not trust the browser's. */
export type JobList = { now: string; jobs: Job[] };

export type PreparedMedia = {
  audio: { duration_s: number | null; sample_rate: number; channels: number; size_bytes: number } | null;
  frames: {
    count: number;
    fps: number | null;
    first_s: number | null;
    last_s: number | null;
    preview: { id: string; t_s: number }[];
  };
  /** First appearance of each distinct picture; null until scene detection has run. */
  scenes: { keyframes: { id: string; t_s: number; scene_index: number }[]; revisits: number } | null;
};

export type TranscriptWord = { text: string; start_s: number; end_s: number; confidence: number | null };

/** The timed transcript from speech-to-text. `available` is false until it has run. */
export type Transcript = {
  available: boolean;
  provider: string | null;
  language: string | null;
  duration_s: number | null;
  word_count: number;
  segments: { start_s: number; end_s: number; text: string; words: TranscriptWord[] }[];
};

/** Text read from each keyframe; boxes are fractions of the frame. */
export type OcrResult = {
  available: boolean;
  keyframes: {
    frame_id: string;
    t_s: number;
    regions: { text: string; confidence: number; x: number; y: number; w: number; h: number }[];
  }[];
};

export type VisualKind = "chart" | "diagram" | "table" | "equation" | "text_block" | "image" | "other";

/** Visual units ranked by how much they need describing (Tasks 12-13). */
export type Visuals = {
  available: boolean;
  scored: boolean;
  units: {
    id: string;
    frame_id: string;
    kind: VisualKind;
    label: string;
    lines: string[];
    details: string;
    x: number | null;
    y: number | null;
    w: number | null;
    h: number | null;
    t_start_s: number;
    t_end_s: number;
    source: string;
    coverage: number | null;
    priority: number | null;
    said: string[];
    unsaid: string[];
  }[];
};

export type Box = { x: number; y: number; w: number; h: number };
export type VerificationState = "verified_text_match" | "corroborated" | "uncertain" | "needs_review";

/** A spoken pointer such as "this line here" and what it was linked to (Task 14). */
export type References = {
  available: boolean;
  references: {
    phrase: string;
    t_s: number;
    status: "linked" | "ambiguous" | "unresolved";
    confidence: number;
    visual_unit_id: string | null;
    label: string | null;
  }[];
};

export type Cue = {
  id: string;
  visual_unit_id: string | null;
  text_short: string;
  text_medium: string | null;
  text_long: string | null;
  anchor_t_s: number;
  priority: number;
  verification_state: VerificationState;
  review_status: "pending" | "approved" | "rejected";
};

export type Cues = { available: boolean; cues: Cue[] };

/** Everything one cue rests on (Task 15). Paths in `image_url` are relative to the API. */
export type CueLedger = {
  cue: Cue;
  evidence: {
    kind: "frame" | "ocr_region" | "slide" | "transcript_span" | "visual_unit";
    note: string | null;
    frame: { id: string; t_s: number; image_url: string } | null;
    ocr_region: { text: string; confidence: number; box: Box } | null;
    slide: { page: number; text: string; score: number | null } | null;
    visual_unit: { kind: VisualKind; label: string; box: Box | null; t_start_s: number; t_end_s: number; coverage: number | null } | null;
    transcript: { start_s: number; end_s: number; text: string } | null;
  }[];
  checks: {
    claim: string;
    check: "quote_match" | "number_match" | "description_support";
    result: "pass" | "fail" | "inconclusive";
    resulting_state: VerificationState;
    detail: { source?: string; reason?: string; ocr_confidence?: number };
  }[];
};

/** The latest speech-safe schedule (Tasks 18-19). */
export type Schedule = {
  available: boolean;
  solver: "greedy" | "cp_sat" | null;
  mode: "standard" | "extended" | null;
  status: "succeeded" | "infeasible" | "failed" | null;
  windows: { start_s: number; end_s: number }[];
  placements: {
    cue_id: string;
    variant: "short" | "medium" | "long";
    text: string;
    start_s: number;
    end_s: number;
    verification_state: VerificationState;
  }[];
  not_placed: { cue_id: string; text: string; reason: string }[];
  priority_placed_share: number | null;
  duration_ms: number | null;
};

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function toApiError(res: Response): Promise<ApiError> {
  try {
    const body = (await res.json()) as { error?: { code?: string; message?: string } };
    if (body.error?.message) return new ApiError(res.status, body.error.code ?? "error", body.error.message);
  } catch {
    // fall through
  }
  return new ApiError(res.status, "http_error", `The server responded with ${res.status}.`);
}

export async function getJson<T>(path: string, init?: RequestInit, base = API_BASE): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${base}${path}`, { cache: "no-store", ...init });
  } catch {
    throw new ApiError(0, "network", "The SeeHere API could not be reached.");
  }
  if (!res.ok) throw await toApiError(res);
  return (await res.json()) as T;
}

/**
 * Cancel or retry a job. The custom header makes the browser send a CORS preflight, which only
 * this app's origin passes, so other sites cannot trigger these actions.
 */
export function jobAction(jobId: string, action: "cancel" | "retry"): Promise<Job> {
  return getJson<Job>(`/api/jobs/${jobId}/${action}`, {
    method: "POST",
    headers: { "X-SeeHere-Request": "1" },
  });
}

/** The optional slide deck and which keyframe each page was matched to. */
export type Deck = {
  available: boolean;
  filename: string | null;
  kind: "pdf" | "pptx" | null;
  ingested: boolean;
  pages: { page: number; text: string; frame_id: string | null; t_s: number | null; score: number | null }[];
};

export function uploadDeck(projectId: string, file: File): Promise<Deck> {
  return getJson<Deck>(`/api/projects/${projectId}/deck`, {
    method: "POST",
    headers: { "X-SeeHere-Request": "1", "X-SeeHere-Filename": encodeURIComponent(file.name) },
    body: file,
  });
}

export function frameImageUrl(frameId: string): string {
  return `${API_BASE}/api/frames/${frameId}/image`;
}

export type UploadPhase = "uploading" | "checking";

export type UploadHandlers = {
  /** Fraction of bytes sent, 0..1. */
  onProgress?: (sent: number, total: number) => void;
  /** "checking" starts when the last byte is sent and the server is inspecting the video. */
  onPhase?: (phase: UploadPhase) => void;
  signal?: AbortSignal;
};

/**
 * Upload a lecture. Uses XMLHttpRequest because fetch() cannot report upload progress.
 * The body is the raw file; metadata goes in URL-encoded headers (see the API docstring).
 */
export function uploadLecture(
  input: { file: File; title: string; rightsConfirmed: boolean },
  { onProgress, onPhase, signal }: UploadHandlers = {},
): Promise<Project> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/api/projects`);
    xhr.setRequestHeader("Content-Type", input.file.type || "application/octet-stream");
    xhr.setRequestHeader("X-SeeHere-Title", encodeURIComponent(input.title));
    xhr.setRequestHeader("X-SeeHere-Filename", encodeURIComponent(input.file.name));
    xhr.setRequestHeader("X-SeeHere-Rights-Confirmed", input.rightsConfirmed ? "true" : "false");
    xhr.responseType = "json";

    onPhase?.("uploading");
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(e.loaded, e.total);
    };
    xhr.upload.onload = () => onPhase?.("checking");

    xhr.onload = () => {
      const body = xhr.response as Project | { error?: { code?: string; message?: string } } | null;
      if (xhr.status === 201 && body && "id" in body) return resolve(body);
      const err = body && "error" in body ? body.error : undefined;
      reject(
        new ApiError(xhr.status, err?.code ?? "http_error", err?.message ?? `Upload failed (${xhr.status}).`),
      );
    };
    xhr.onerror = () => reject(new ApiError(0, "network", "The upload was interrupted. Check your connection."));
    xhr.onabort = () => reject(new ApiError(0, "aborted", "Upload cancelled."));

    if (signal) {
      if (signal.aborted) return xhr.abort();
      signal.addEventListener("abort", () => xhr.abort(), { once: true });
    }
    xhr.send(input.file);
  });
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i++;
  }
  return `${value < 10 ? value.toFixed(1) : Math.round(value)} ${units[i]}`;
}

/** 75.4 → "1:15"; 3725 → "1:02:05". */
export function formatDuration(seconds: number): string {
  const s = Math.round(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
}

/** A limit in words: 600 → "10 minutes"; 10800 → "3 hours"; 90 → "90 seconds". */
export function formatDurationLimit(seconds: number): string {
  const plural = (n: number, unit: string) => `${n} ${unit}${n === 1 ? "" : "s"}`;
  if (seconds % 3600 === 0) return plural(seconds / 3600, "hour");
  if (seconds % 60 === 0) return plural(seconds / 60, "minute");
  return plural(seconds, "second");
}

/** Title suggestion from a filename: "lecture_07-graphs.mp4" → "lecture 07 graphs". */
export function titleFromFilename(name: string): string {
  return name
    .replace(/\.[^.]+$/, "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 200);
}

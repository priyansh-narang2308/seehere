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

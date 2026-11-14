import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, formatBytes, formatDuration, formatDurationLimit, getJson, titleFromFilename, uploadLecture, type Project } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("formatBytes", () => {
  it.each([
    [0, "0 B"],
    [1023, "1023 B"],
    [1024, "1.0 KB"],
    [1536, "1.5 KB"],
    [5 * 1024 * 1024, "5.0 MB"],
    [500 * 1024 * 1024, "500 MB"],
    [3 * 1024 ** 3, "3.0 GB"],
  ])("%d bytes → %s", (bytes, text) => expect(formatBytes(bytes)).toBe(text));
});

describe("formatDuration", () => {
  it.each([
    [0, "0:00"],
    [5.4, "0:05"],
    [75.4, "1:15"],
    [3600, "1:00:00"],
    [3725, "1:02:05"],
  ])("%d s → %s", (s, text) => expect(formatDuration(s)).toBe(text));
});

describe("formatDurationLimit", () => {
  it.each([
    [600, "10 minutes"],
    [60, "1 minute"],
    [3600, "1 hour"],
    [10800, "3 hours"],
    [90, "90 seconds"],
  ])("%d s → %s", (s, text) => expect(formatDurationLimit(s)).toBe(text));
});

describe("titleFromFilename", () => {
  it("drops the extension and separators", () => {
    expect(titleFromFilename("lecture_07--graphs.final.mp4")).toBe("lecture 07 graphs.final");
  });
  it("caps the length at 200 characters", () => {
    expect(titleFromFilename(`${"a".repeat(300)}.mp4`)).toHaveLength(200);
  });
});

describe("getJson", () => {
  it("returns parsed JSON on success", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ ok: 1 })));
    await expect(getJson("/x")).resolves.toEqual({ ok: 1 });
  });

  it("maps the API error shape to ApiError", async () => {
    const body = { error: { code: "not_found", message: "Project not found." } };
    vi.stubGlobal("fetch", vi.fn(async () => Response.json(body, { status: 404 })));
    await expect(getJson("/x")).rejects.toMatchObject({ status: 404, code: "not_found", message: "Project not found." });
  });

  it("falls back to a generic message for non-JSON errors", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("boom", { status: 502 })));
    await expect(getJson("/x")).rejects.toMatchObject({ status: 502, code: "http_error" });
  });

  it("reports an unreachable API as a network error", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("fetch failed"))));
    const err = await getJson("/x").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 0, code: "network" });
  });
});

/** Minimal XMLHttpRequest double: records the request and lets the test drive its events. */
class FakeXHR {
  static last: FakeXHR;
  method = "";
  url = "";
  headers: Record<string, string> = {};
  body: unknown;
  status = 0;
  response: unknown = null;
  responseType = "";
  aborted = false;
  upload: { onprogress?: (e: ProgressEvent) => void; onload?: () => void } = {};
  onload?: () => void;
  onerror?: () => void;
  onabort?: () => void;
  constructor() {
    FakeXHR.last = this;
  }
  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }
  setRequestHeader(k: string, v: string) {
    this.headers[k] = v;
  }
  send(body: unknown) {
    this.body = body;
  }
  abort() {
    this.aborted = true;
    this.onabort?.();
  }
  respond(status: number, response: unknown) {
    this.status = status;
    this.response = response;
    this.onload?.();
  }
}

const file = new File(["video-bytes"], "Lecture 7 – Graphs.mp4", { type: "video/mp4" });

describe("uploadLecture", () => {
  it("sends the raw file with encoded metadata headers and reports progress and phases", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXHR);
    const onProgress = vi.fn();
    const onPhase = vi.fn();
    const promise = uploadLecture({ file, title: "Graphs & charts", rightsConfirmed: true }, { onProgress, onPhase });
    const xhr = FakeXHR.last;

    expect(xhr.method).toBe("POST");
    expect(xhr.url).toMatch(/\/api\/projects$/);
    expect(xhr.body).toBe(file);
    expect(xhr.headers).toMatchObject({
      "Content-Type": "video/mp4",
      "X-SeeHere-Request": "1",
      "X-SeeHere-Title": "Graphs%20%26%20charts",
      "X-SeeHere-Filename": encodeURIComponent("Lecture 7 – Graphs.mp4"),
      "X-SeeHere-Rights-Confirmed": "true",
    });

    xhr.upload.onprogress?.({ lengthComputable: true, loaded: 5, total: 11 } as ProgressEvent);
    xhr.upload.onload?.();
    const project = { id: "p1", title: "Graphs & charts" } as Project;
    xhr.respond(201, project);

    await expect(promise).resolves.toEqual(project);
    expect(onProgress).toHaveBeenCalledWith(5, 11);
    expect(onPhase.mock.calls.map((c) => c[0])).toEqual(["uploading", "checking"]);
  });

  it("rejects with the server's error code and message", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXHR);
    const promise = uploadLecture({ file, title: "t", rightsConfirmed: true });
    FakeXHR.last.respond(415, { error: { code: "unsupported_format", message: "Not a supported video." } });
    await expect(promise).rejects.toMatchObject({ status: 415, code: "unsupported_format", message: "Not a supported video." });
  });

  it("aborts the request when the signal fires", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXHR);
    const controller = new AbortController();
    const promise = uploadLecture({ file, title: "t", rightsConfirmed: true }, { signal: controller.signal });
    controller.abort();
    await expect(promise).rejects.toMatchObject({ code: "aborted" });
    expect(FakeXHR.last.aborted).toBe(true);
  });

  it("reports a dropped connection as a network error", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXHR);
    const promise = uploadLecture({ file, title: "t", rightsConfirmed: true });
    FakeXHR.last.onerror?.();
    await expect(promise).rejects.toMatchObject({ code: "network" });
  });
});

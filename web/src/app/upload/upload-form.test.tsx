import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/ui/toast";
import type { Project, UploadConfig } from "@/lib/api";
import { UploadForm, validateUpload } from "./upload-form";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const uploadLecture = vi.fn();
vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<typeof import("@/lib/api")>()),
  uploadLecture: (...args: unknown[]) => uploadLecture(...args),
}));

const config: UploadConfig = {
  max_upload_bytes: 1024 * 1024,
  max_video_duration_s: 3 * 3600,
  accept: ".mp4,.mov,.webm,.mkv",
  formats: ["MP4", "MOV", "WebM", "MKV"],
  retention_hours: 24,
};

const video = (size = 2048, name = "lecture_07-graphs.mp4") =>
  new File([new Uint8Array(size)], name, { type: "video/mp4" });

describe("validateUpload", () => {
  it("requires a title, a file and the rights confirmation", () => {
    expect(validateUpload({ title: "  ", file: null, rights: false }, config)).toEqual({
      title: "Enter a title for this lecture.",
      file: "Choose a video file.",
      rights: "Confirm that you may process this video.",
    });
  });

  it("rejects empty and oversized files and long titles", () => {
    expect(validateUpload({ title: "x".repeat(201), file: video(0), rights: true }, config)).toEqual({
      title: "Use 200 characters or fewer.",
      file: "This file is empty.",
    });
    expect(validateUpload({ title: "ok", file: video(2 * 1024 * 1024), rights: true }, config).file).toBe(
      "This file is 2.0 MB. The limit is 1.0 MB.",
    );
  });

  it("passes a valid upload, and skips the size check when limits are unknown", () => {
    expect(validateUpload({ title: "ok", file: video(), rights: true }, config)).toEqual({});
    expect(validateUpload({ title: "ok", file: video(2 * 1024 * 1024), rights: true }, null)).toEqual({});
  });
});

describe("UploadForm", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json(config)));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    push.mockReset();
    uploadLecture.mockReset();
  });

  const renderForm = () =>
    render(
      <ToastProvider>
        <UploadForm />
      </ToastProvider>,
    );

  it("shows the server's limits and retention once loaded", async () => {
    renderForm();
    expect(await screen.findByText(/up to 1\.0 MB and 3 hours long/)).toBeInTheDocument();
    expect(screen.getByText(/expire after 24 hours\. Automatic deletion is not built yet/)).toBeInTheDocument();
    expect(screen.getByLabelText(/video file/i)).toHaveAttribute("accept", config.accept);
  });

  it("lists every problem and focuses the first invalid field", async () => {
    const user = userEvent.setup();
    renderForm();
    await screen.findByText(/up to 1\.0 MB/);
    await user.click(screen.getByRole("button", { name: /upload lecture/i }));

    expect(screen.getByText("Enter a title for this lecture.")).toBeInTheDocument();
    expect(screen.getByText("Choose a video file.")).toBeInTheDocument();
    expect(screen.getByText("Confirm that you may process this video.")).toBeInTheDocument();
    expect(screen.getByLabelText(/video file/i)).toHaveFocus();
    expect(screen.getByRole("checkbox")).toHaveAccessibleDescription("Confirm that you may process this video.");
    expect(uploadLecture).not.toHaveBeenCalled();

    // Choosing a file fills the empty title, so its error clears too.
    await user.upload(screen.getByLabelText(/video file/i), video());
    expect(screen.queryByText("Enter a title for this lecture.")).toBeNull();
    expect(screen.queryByText("Choose a video file.")).toBeNull();
  });

  it("uploads, shows progress, then goes to the project's processing page", async () => {
    const user = userEvent.setup();
    let finish: (p: Project) => void = () => {};
    uploadLecture.mockImplementation(
      (_input, handlers: { onProgress: (a: number, b: number) => void }) =>
        new Promise<Project>((resolve) => {
          handlers.onProgress(1024, 2048);
          finish = resolve;
        }),
    );
    renderForm();
    await screen.findByText(/up to 1\.0 MB/);

    await user.upload(screen.getByLabelText(/video file/i), video());
    expect(screen.getByLabelText(/lecture title/i)).toHaveValue("lecture 07 graphs");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: /upload lecture/i }));

    expect(uploadLecture).toHaveBeenCalledWith(
      expect.objectContaining({ title: "lecture 07 graphs", rightsConfirmed: true }),
      expect.anything(),
    );
    expect(await screen.findByText("1.0 KB of 2.0 KB")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Upload progress" })).toHaveAttribute("aria-valuenow", "50");
    expect(screen.getByRole("button", { name: /cancel upload/i })).toBeInTheDocument();

    finish({ id: "0b8f7c1e-1d2a-4c3b-9e8f-7a6b5c4d3e2f", title: "lecture 07 graphs" } as Project);
    await waitFor(() => expect(push).toHaveBeenCalledWith("/projects/0b8f7c1e-1d2a-4c3b-9e8f-7a6b5c4d3e2f/processing"));
    expect(await screen.findByText("Upload complete")).toBeInTheDocument();
  });

  it("shows the server's reason when the upload is refused", async () => {
    const { ApiError } = await import("@/lib/api");
    uploadLecture.mockRejectedValue(new ApiError(422, "no_audio_stream", "This video has no audio track."));
    const user = userEvent.setup();
    renderForm();
    await screen.findByText(/up to 1\.0 MB/);
    await user.upload(screen.getByLabelText(/video file/i), video());
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: /upload lecture/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("This video has no audio track.");
    expect(push).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /upload lecture/i })).toBeEnabled();
  });

  it("still allows uploading when the limits cannot be loaded", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("down"))));
    renderForm();
    expect(await screen.findByText(/could not be reached\. The server will still enforce its limits/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/video file/i), { target: { files: [video()] } });
    expect(screen.getByLabelText(/lecture title/i)).toHaveValue("lecture 07 graphs");
  });
});

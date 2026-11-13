"use client";

import { FileVideo, TriangleAlert, Upload, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox, Field, Input } from "@/components/ui/field";
import { Progress } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import {
  ApiError,
  formatBytes,
  formatDurationLimit,
  getJson,
  titleFromFilename,
  uploadLecture,
  type UploadConfig,
} from "@/lib/api";

type Errors = Partial<Record<"title" | "file" | "rights", string>>;
type State =
  | { kind: "idle" }
  | { kind: "uploading"; sent: number; total: number }
  | { kind: "checking" }
  | { kind: "error"; message: string };

export function validateUpload(
  values: { title: string; file: File | null; rights: boolean },
  config: UploadConfig | null,
): Errors {
  const errors: Errors = {};
  const title = values.title.trim();
  if (!title) errors.title = "Enter a title for this lecture.";
  else if (title.length > 200) errors.title = "Use 200 characters or fewer.";
  if (!values.file) errors.file = "Choose a video file.";
  else if (values.file.size === 0) errors.file = "This file is empty.";
  else if (config && values.file.size > config.max_upload_bytes)
    errors.file = `This file is ${formatBytes(values.file.size)}. The limit is ${formatBytes(config.max_upload_bytes)}.`;
  if (!values.rights) errors.rights = "Confirm that you may process this video.";
  return errors;
}

export function UploadForm() {
  const router = useRouter();
  const { toast } = useToast();
  const [config, setConfig] = useState<UploadConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [rights, setRights] = useState(false);
  const [errors, setErrors] = useState<Errors>({});
  const [state, setState] = useState<State>({ kind: "idle" });
  const abortRef = useRef<AbortController | null>(null);
  const titleRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const rightsRef = useRef<HTMLInputElement>(null);
  const rightsErrorId = useId();
  const busy = state.kind === "uploading" || state.kind === "checking";

  useEffect(() => {
    const controller = new AbortController();
    getJson<UploadConfig>("/api/config/upload", { signal: controller.signal })
      .then(setConfig)
      .catch((e: unknown) => {
        if (!controller.signal.aborted) setConfigError(e instanceof ApiError ? e.message : "Could not load upload limits.");
      });
    return () => controller.abort();
  }, []);

  // Cancel an in-flight upload if the user leaves the page.
  useEffect(() => () => abortRef.current?.abort(), []);

  function onFileChange(next: File | null) {
    setFile(next);
    setErrors((e) => ({ ...e, file: undefined }));
    if (next && !title.trim()) {
      setTitle(titleFromFilename(next.name));
      setErrors((e) => ({ ...e, title: undefined }));
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const found = validateUpload({ title, file, rights }, config);
    setErrors(found);
    // Focus the first invalid field in page order.
    if (found.file) return fileRef.current?.focus();
    if (found.title) return titleRef.current?.focus();
    if (found.rights) return rightsRef.current?.focus();
    if (!file) return;

    const controller = new AbortController();
    abortRef.current = controller;
    setState({ kind: "uploading", sent: 0, total: file.size });
    try {
      const project = await uploadLecture(
        { file, title: title.trim(), rightsConfirmed: rights },
        {
          signal: controller.signal,
          onProgress: (sent, total) => setState({ kind: "uploading", sent, total }),
          onPhase: (phase) => phase === "checking" && setState({ kind: "checking" }),
        },
      );
      toast({ title: "Upload complete", description: `“${project.title}” was uploaded and checked.`, tone: "success" });
      router.push(`/projects/${project.id}/processing`);
    } catch (err) {
      if (err instanceof ApiError && err.code === "aborted") {
        setState({ kind: "idle" });
        toast({ title: "Upload cancelled", tone: "info" });
        return;
      }
      setState({ kind: "error", message: err instanceof Error ? err.message : "Upload failed." });
    } finally {
      abortRef.current = null;
    }
  }

  const percent = state.kind === "uploading" && state.total > 0 ? (state.sent / state.total) * 100 : undefined;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
      <form
        noValidate
        onSubmit={onSubmit}
        aria-busy={busy}
        className="grid gap-5 rounded-lg border border-border bg-surface p-5 shadow-card sm:p-6"
      >
        <Field label="Video file" required error={errors.file} hint={config ? `${config.formats.join(", ")} · up to ${formatBytes(config.max_upload_bytes)} and ${formatDurationLimit(config.max_video_duration_s)} long` : "MP4, MOV, WebM or MKV"}>
          <Input
            ref={fileRef}
            type="file"
            accept={config?.accept ?? "video/*"}
            disabled={busy}
            onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
            className="h-auto cursor-pointer py-2 file:mr-3 file:cursor-pointer file:rounded-sm file:border-0 file:bg-sunken file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-ink"
          />
        </Field>
        {file && (
          <p className="-mt-2 flex items-center gap-2 text-sm text-ink-2">
            <FileVideo aria-hidden="true" className="size-4 text-muted" />
            <span className="truncate">{file.name}</span>
            <span className="shrink-0 font-mono text-xs text-muted">{formatBytes(file.size)}</span>
          </p>
        )}

        <Field label="Lecture title" required error={errors.title} hint="Shown on the project and in exports.">
          <Input
            ref={titleRef}
            value={title}
            maxLength={200}
            disabled={busy}
            onChange={(e) => {
              setTitle(e.target.value);
              setErrors((x) => ({ ...x, title: undefined }));
            }}
            placeholder="Intro to Data Analysis, Lecture 7"
          />
        </Field>

        <div>
          <Checkbox
            ref={rightsRef}
            checked={rights}
            disabled={busy}
            required
            aria-invalid={errors.rights ? true : undefined}
            aria-describedby={errors.rights ? rightsErrorId : undefined}
            onChange={(e) => {
              setRights(e.target.checked);
              setErrors((x) => ({ ...x, rights: undefined }));
            }}
            label="I own this video or have permission to process it."
          />
          {errors.rights && (
            <p id={rightsErrorId} className="mt-1.5 ml-6.5 text-xs font-medium text-danger">
              {errors.rights}
            </p>
          )}
        </div>

        <div role="status" aria-live="polite" className="empty:hidden">
          {state.kind === "uploading" && (
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="font-medium text-ink">Uploading</span>
                <span className="font-mono text-muted">
                  {formatBytes(state.sent)} of {formatBytes(state.total)}
                </span>
              </div>
              <Progress label="Upload progress" value={percent} />
            </div>
          )}
          {state.kind === "checking" && (
            <div className="space-y-2">
              <p className="text-sm font-medium text-ink">Checking the video…</p>
              <Progress label="Checking the video" valueText="Checking the video" />
            </div>
          )}
        </div>

        {state.kind === "error" && (
          <div role="alert" className="flex gap-2 rounded-md border border-danger-line bg-danger-soft px-3 py-2.5 text-sm text-danger">
            <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            <span>{state.message}</span>
          </div>
        )}
        {configError && (
          <p role="alert" className="text-sm text-warning">
            {configError} The server will still enforce its limits.
          </p>
        )}

        <div className="flex flex-wrap gap-3">
          <Button type="submit" loading={busy}>
            <Upload aria-hidden="true" />
            {busy ? "Uploading" : "Upload lecture"}
          </Button>
          {state.kind === "uploading" && (
            <Button variant="secondary" onClick={() => abortRef.current?.abort()}>
              <X aria-hidden="true" /> Cancel upload
            </Button>
          )}
        </div>
      </form>

      <aside aria-labelledby="needs" className="h-fit rounded-lg border border-border bg-surface p-5 shadow-card">
        <h2 id="needs" className="font-semibold text-ink">
          Before you upload
        </h2>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-ink-2 marker:text-muted">
          <li>Use a lecture video that you own, or have permission to process.</li>
          <li>The video needs an audio track: SeeHere listens to the lecturer to find gaps and pointers.</li>
          <li>The file is checked by its content, not its name. Playlists and other formats are refused.</li>
          {config && (
            <li>
              The video and everything made from it are deleted {config.retention_hours} hours after upload.
            </li>
          )}
        </ul>
      </aside>
    </div>
  );
}

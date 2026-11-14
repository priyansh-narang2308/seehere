"use client";

import { Download, ListChecks } from "lucide-react";
import { useEffect, useState } from "react";
import { DescribedPlayer } from "@/components/player/described-player";
import { EmptyState } from "@/components/ui/empty-state";
import { apiUrl, formatBytes, getJson, type ExportFile, type Exports, type Schedule, type Transcript } from "@/lib/api";
import type { PlayCue } from "@/lib/playback";

const FILE_LABELS: Record<ExportFile["kind"], string> = {
  bundle_zip: "Everything (zip)",
  standard_mp4: "Described video, standard",
  extended_mp4: "Described video, extended (pauses)",
  webvtt: "WebVTT description track",
  transcript_html: "Accessible transcript (HTML)",
  cue_audio_zip: "Description audio clips (zip)",
  manifest_json: "Evidence manifest (JSON)",
};

const toCues = (s: Schedule | null): PlayCue[] | null =>
  s?.available && s.status === "succeeded"
    ? s.placements.map((p) => ({
        id: p.cue_id,
        text: p.text,
        start: p.start_s,
        length: p.audio_s ?? p.end_s - p.start_s,
        pause: p.pause_s,
        audioUrl: p.audio_url ? apiUrl(p.audio_url) : null,
      }))
    : null;

type Loaded = { standard: Schedule; extended: Schedule; transcript: Transcript; exports: Exports };

/** The described lecture: a player, and the files to publish. */
export function ResultsView({ projectId, title }: { projectId: string; title: string }) {
  const [data, setData] = useState<Loaded | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const get = <T,>(path: string) => getJson<T>(`/api/projects/${projectId}${path}`, { signal: controller.signal });
    Promise.all([get<Schedule>("/schedule"), get<Schedule>("/schedule?mode=extended"), get<Transcript>("/transcript"), get<Exports>("/exports")])
      .then(([standard, extended, transcript, exports]) => setData({ standard, extended, transcript, exports }))
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true);
      });
    return () => controller.abort();
  }, [projectId]);

  if (failed) {
    return (
      <p role="alert" className="mt-8 text-sm text-danger">
        The results could not be loaded. Check that the SeeHere API is running, then reload.
      </p>
    );
  }
  if (!data) return <p className="mt-8 text-sm text-muted">Loading results…</p>;
  const standard = toCues(data.standard);
  if (!standard || !data.exports.available) {
    return (
      <EmptyState
        className="mt-8"
        icon={ListChecks}
        title="No results yet"
        description="Results appear when processing has scheduled, voiced, checked and exported the descriptions. Follow progress on the Processing tab."
      />
    );
  }
  const order = Object.keys(FILE_LABELS);
  const files = [...data.exports.files].sort((a, b) => order.indexOf(a.kind) - order.indexOf(b.kind));
  return (
    <div className="mt-8 space-y-10">
      <section aria-labelledby="player">
        <h2 id="player" className="mb-3 text-lg font-semibold tracking-tight text-ink">
          Described lecture
        </h2>
        <DescribedPlayer
          videoUrl={apiUrl(`/api/projects/${projectId}/video`)}
          cues={{ standard, extended: toCues(data.extended) }}
          speech={data.transcript.available ? data.transcript.segments : []}
          title={title}
        />
      </section>
      <section aria-labelledby="downloads">
        <h2 id="downloads" className="text-lg font-semibold tracking-tight text-ink">
          Downloads
        </h2>
        <p className="mt-1 text-sm text-muted">
          Review every description before publishing. Verification checks quoted text and numbers against the on-screen text; it is not complete fact-checking, and these files are not a WCAG conformance certification.
        </p>
        <ul aria-label="Export files" className="mt-3 divide-y divide-border rounded-lg border border-border">
          {files.map((f) => (
            <li key={f.id} className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
              <span className="min-w-0">
                <span className="block text-ink">{FILE_LABELS[f.kind]}</span>
                <span className="font-mono text-xs text-muted">
                  {f.filename} · {formatBytes(f.size_bytes)}
                </span>
              </span>
              <a href={apiUrl(f.url)} download={f.filename} className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-accent-strong hover:bg-sunken">
                <Download aria-hidden="true" className="size-4" />
                Download <span className="sr-only">{FILE_LABELS[f.kind]}</span>
              </a>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

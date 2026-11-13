import { CheckCircle2 } from "lucide-react";
import { formatBytes, formatDuration, type Project } from "@/lib/api";
import { ProjectStatusBadge } from "./project-status-badge";

const dateFormat = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" });

/** What the server measured about the uploaded video (from ffprobe), not what the client claimed. */
export function SourceFacts({ project }: { project: Project }) {
  const s = project.source;
  const facts: [string, string][] = s
    ? [
        ["File", s.original_filename],
        ["Length", s.duration_s != null ? formatDuration(s.duration_s) : "Unknown"],
        ["Resolution", s.width && s.height ? `${s.width} × ${s.height}` : "Unknown"],
        ["Size", formatBytes(s.size_bytes)],
        ["Format", s.mime_type],
        ["Codecs", [s.video_codec, s.audio_codec].filter(Boolean).join(" + ")],
      ]
    : [];
  return (
    <section aria-labelledby="source-heading" className="rounded-lg border border-border bg-surface shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4">
        <h2 id="source-heading" className="flex items-center gap-2 font-semibold text-ink">
          <CheckCircle2 aria-hidden="true" className="size-4 text-success" />
          Upload checked
        </h2>
        <ProjectStatusBadge status={project.status} />
      </div>
      {s ? (
        <dl className="grid gap-x-6 gap-y-3 px-5 py-4 text-sm sm:grid-cols-3">
          {facts.map(([k, v]) => (
            <div key={k} className="min-w-0">
              <dt className="text-muted">{k}</dt>
              <dd className="mt-0.5 truncate font-medium text-ink" title={v}>
                {v}
              </dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="px-5 py-4 text-sm text-muted">No source video is attached to this project.</p>
      )}
      {project.expires_at && (
        <p className="border-t border-border px-5 py-3 text-xs text-muted">
          Scheduled for deletion on <time dateTime={project.expires_at}>{dateFormat.format(new Date(project.expires_at))} UTC</time>.
        </p>
      )}
    </section>
  );
}

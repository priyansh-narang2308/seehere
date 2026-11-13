"use client";

import { FolderOpen, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ApiError, formatBytes, formatDuration, getJson, type Project } from "@/lib/api";
import { ProjectStatusBadge } from "./project-status-badge";

type State = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ready"; projects: Project[] };

const dateFormat = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" });

export function ProjectList() {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getJson<Project[]>("/api/projects", { signal: controller.signal })
      .then((projects) => setState({ kind: "ready", projects }))
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setState({ kind: "error", message: e instanceof ApiError ? e.message : "Could not load projects." });
      });
    return () => controller.abort();
  }, [attempt]);

  if (state.kind === "loading") {
    return (
      <p role="status" className="mt-8 text-sm text-muted">
        Loading projects…
      </p>
    );
  }
  if (state.kind === "error") {
    return (
      <EmptyState className="mt-8" icon={TriangleAlert} title="Projects could not be loaded" description={state.message}>
        <Button
          variant="secondary"
          onClick={() => {
            setState({ kind: "loading" });
            setAttempt((n) => n + 1);
          }}
        >
          Try again
        </Button>
      </EmptyState>
    );
  }
  if (state.projects.length === 0) {
    return (
      <EmptyState
        className="mt-8"
        icon={FolderOpen}
        title="No projects yet"
        description="Upload a lecture to create your first project."
      >
        <Button asChild>
          <Link href="/upload">Upload a lecture</Link>
        </Button>
      </EmptyState>
    );
  }

  return (
    <ul className="mt-8 divide-y divide-border rounded-lg border border-border bg-surface shadow-card">
      {state.projects.map((p) => (
        <li key={p.id} className="relative flex flex-col gap-2 px-5 py-4 hover:bg-surface-muted sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <h2 className="truncate font-medium text-ink">
              <Link href={`/projects/${p.id}/processing`} className="after:absolute after:inset-0 focus-visible:outline-none">
                {p.title}
              </Link>
            </h2>
            <p className="mt-0.5 text-sm text-muted">
              Uploaded <time dateTime={p.created_at}>{dateFormat.format(new Date(p.created_at))}</time>
              {p.source?.duration_s != null && <> · {formatDuration(p.source.duration_s)}</>}
              {p.source && <> · {formatBytes(p.source.size_bytes)}</>}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {p.source && <Badge shape="tag">{p.source.mime_type.replace("video/", "").toUpperCase()}</Badge>}
            <ProjectStatusBadge status={p.status} />
          </div>
        </li>
      ))}
    </ul>
  );
}

"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Eyebrow } from "@/components/ui/card";

type ComponentHealth = { status: "ok" | "degraded" | "down"; detail: string; latency_ms?: number | null };
type HealthReport = {
  status: "ok" | "degraded" | "down";
  version: string;
  environment: string;
  components: Record<string, ComponentHealth>;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

const tone = { ok: "success", degraded: "warning", down: "danger" } as const;

export function BackendStatus() {
  const [report, setReport] = useState<HealthReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_BASE}/api/health`, { signal: controller.signal, cache: "no-store" })
      .then(async (r) => setReport((await r.json()) as HealthReport))
      .catch((e: unknown) => {
        if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "request failed");
      });
    return () => controller.abort();
  }, []);

  return (
    <section aria-labelledby="status-heading" className="w-full max-w-xl">
      <Eyebrow as="h2" id="status-heading">
        System status
      </Eyebrow>
      <div role="status" aria-live="polite" className="mt-3">
        {error && <p className="text-sm text-danger">API unreachable: {error}</p>}
        {!error && !report && <p className="text-sm text-muted">Checking the API…</p>}
        {report && (
          <ul className="divide-y divide-border rounded-lg border border-border bg-surface shadow-card">
            <li className="flex items-center justify-between px-4 py-3 text-sm">
              <span className="font-medium text-ink">API v{report.version}</span>
              <Badge tone={tone[report.status]}>{report.status}</Badge>
            </li>
            {Object.entries(report.components).map(([name, c]) => (
              <li key={name} className="flex items-center justify-between gap-4 px-4 py-2.5 text-sm">
                <span className="text-ink-2">{name}</span>
                <span className="flex min-w-0 items-center gap-3">
                  <span className="truncate text-xs text-muted" title={c.detail}>{c.detail}</span>
                  <Badge tone={tone[c.status]} className="shrink-0">
                    {c.status}
                  </Badge>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

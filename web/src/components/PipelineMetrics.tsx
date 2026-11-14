"use client";

import { useEffect, useState } from "react";
import { Eyebrow } from "@/components/ui/card";
import { getJson, type MetricsSummary } from "@/lib/api";

export const STAGE_LABEL: Record<string, string> = {
  "media.prepare": "Prepare media",
  "speech.transcribe": "Transcribe speech",
  "scenes.detect": "Detect slide changes",
  "ocr.extract": "Read on-screen text",
  "deck.ingest": "Read slide deck",
  "visual.analyze": "Find visuals",
  "coverage.score": "Check what was said",
  "references.resolve": "Resolve references",
  "descriptions.generate": "Write descriptions",
  "claims.verify": "Verify claims",
  "schedule.plan": "Plan timing",
  "speech.synthesize": "Voice descriptions",
  "timing.check": "Check timing",
  "export.build": "Build exports",
};

const OPERATION_LABEL: Record<string, string> = {
  vision: "Vision model",
  tts: "Text to speech",
  stt: "Speech to text",
};

const seconds = (s: number) => (s < 10 ? s.toFixed(2) : s.toFixed(1));

const ORDER = Object.keys(STAGE_LABEL);

/** Stages in the order the pipeline runs them; unknown kinds go last. */
export function inPipelineOrder<T extends { kind: string }>(stages: T[]): T[] {
  const rank = (k: string) => (ORDER.includes(k) ? ORDER.indexOf(k) : ORDER.length);
  return [...stages].sort((a, b) => rank(a.kind) - rank(b.kind) || a.kind.localeCompare(b.kind));
}

export function PipelineMetrics() {
  const [data, setData] = useState<MetricsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getJson<MetricsSummary>("/api/metrics", { signal: controller.signal })
      .then(setData)
      .catch((e: unknown) => {
        if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "request failed");
      });
    return () => controller.abort();
  }, []);

  return (
    <section aria-labelledby="metrics-heading" className="w-full max-w-3xl">
      <Eyebrow as="h2" id="metrics-heading">
        Pipeline performance
      </Eyebrow>
      <p className="mt-2 text-sm text-muted">
        Measured on this server for every job still stored. Projects, and their measurements, are deleted after the retention period.
      </p>
      <div role="status" aria-live="polite" className="mt-3">
        {error && <p className="text-sm text-danger">Metrics unavailable: {error}</p>}
        {!error && !data && <p className="text-sm text-muted">Loading measurements…</p>}
        {data && data.stages.length === 0 && <p className="text-sm text-muted">No jobs have run yet.</p>}
      </div>
      {data && data.stages.length > 0 && (
        <div className="mt-3 overflow-x-auto rounded-lg border border-border bg-surface shadow-card">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Run time per pipeline stage, in seconds</caption>
            <thead className="border-b border-border text-xs text-muted">
              <tr>
                <th scope="col" className="px-4 py-2 font-medium">Stage</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">Runs</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">Median (s)</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">95th pct (s)</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">Slowest (s)</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">Not succeeded</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {inPipelineOrder(data.stages).map((st) => (
                <tr key={st.kind}>
                  <th scope="row" className="px-4 py-2 font-normal text-ink">
                    {STAGE_LABEL[st.kind] ?? st.kind}
                  </th>
                  <td className="px-3 py-2 text-right tabular-nums">{st.attempts}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{seconds(st.p50_run_s)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{seconds(st.p95_run_s)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{seconds(st.max_run_s)}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{st.failed}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data && (
        <div className="mt-6">
          <h3 className="text-sm font-medium text-ink">Hosted model calls</h3>
          {data.providers.length === 0 ? (
            <p className="mt-1 text-sm text-muted">
              None recorded. Every stage ran on local tools, so no API credit was used.
            </p>
          ) : (
            <ul className="mt-2 space-y-1 text-sm text-ink-2">
              {data.providers.map((p) => (
                <li key={p.operation}>
                  {OPERATION_LABEL[p.operation] ?? p.operation}: {p.calls} {p.calls === 1 ? "call" : "calls"}
                  {p.failed > 0 && `, ${p.failed} failed (not billed)`}, mean {p.mean_latency_ms} ms,{" "}
                  {p.estimated_cost_usd === null
                    ? "cost not estimated (no price set)"
                    : `about $${p.estimated_cost_usd.toFixed(4)}`}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}

import { render, screen } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PipelineMetrics } from "./PipelineMetrics";
import type { MetricsSummary } from "@/lib/api";

afterEach(() => vi.unstubAllGlobals());

const summary: MetricsSummary = {
  stages: [
    {
      kind: "speech.synthesize",
      attempts: 2,
      failed: 1,
      p50_run_s: 8.6,
      p95_run_s: 11.23,
      max_run_s: 11.23,
      mean_cpu_s: 15,
      max_peak_rss_mb: 1699,
    },
    {
      kind: "speech.transcribe",
      attempts: 3,
      failed: 0,
      p50_run_s: 38.78,
      p95_run_s: 114.24,
      max_run_s: 114.24,
      mean_cpu_s: 234,
      max_peak_rss_mb: 1699,
    },
  ],
  providers: [
    { operation: "tts", calls: 2, failed: 1, units: { input_chars: 60 }, mean_latency_ms: 120, estimated_cost_usd: null },
  ],
  prices_configured: false,
};

describe("PipelineMetrics", () => {
  it("shows measured stage timings and never invents a cost", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json(summary)));
    const { container } = render(<PipelineMetrics />);
    const row = await screen.findByRole("row", { name: /Transcribe speech/ });
    expect(row).toHaveTextContent("38.8");
    expect(row).toHaveTextContent("114.2");
    expect(screen.getByRole("row", { name: /Voice descriptions/ })).toHaveTextContent("8.60");
    const order = screen.getAllByRole("rowheader").map((h) => h.textContent);
    expect(order).toEqual(["Transcribe speech", "Voice descriptions"]);
    expect(screen.getByText(/1 failed \(not billed\)/)).toBeInTheDocument();
    expect(screen.getByText(/cost not estimated \(no price set\)/)).toBeInTheDocument();
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });

  it("says plainly when nothing was run or called", async () => {
    const empty: MetricsSummary = { stages: [], providers: [], prices_configured: false };
    vi.stubGlobal("fetch", vi.fn(async () => Response.json(empty)));
    render(<PipelineMetrics />);
    expect(await screen.findByText("No jobs have run yet.")).toBeInTheDocument();
    expect(screen.getByText(/no API credit was used/)).toBeInTheDocument();
  });
});

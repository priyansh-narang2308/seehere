import { render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Exports, Schedule, Transcript } from "@/lib/api";
import { ResultsView } from "./results-view";

const P = "p1";
const base: Omit<Schedule, "mode" | "placements"> = { available: true, solver: "cp_sat", status: "succeeded", windows: [], not_placed: [], priority_placed_share: 1, duration_ms: 1, pause_budget_s: null, paused_s: null, extended_duration_s: null, comparison: null };
const placement: Schedule["placements"][number] = { cue_id: "c1", variant: "short", text: "On screen: “Next steps”.", start_s: 11.09, end_s: 12.9, verification_state: "verified_text_match", pause_s: 0, pause_reason: null, audio_url: "/api/audio/x", audio_s: 1.8 };
const standard: Schedule = { ...base, mode: "standard", placements: [placement] };
const transcript: Transcript = { available: true, provider: "whisper", language: "en", duration_s: 15, word_count: 3, segments: [{ start_s: 0, end_s: 2, text: "Hello there.", words: [] }] };
const exports: Exports = {
  available: true,
  files: [
    { id: "e1", kind: "webvtt", filename: "descriptions.vtt", size_bytes: 120, sha256: "x", url: "/api/exports/e1", created_at: "2026-11-14T10:00:00Z" },
    { id: "e2", kind: "bundle_zip", filename: "seehere-export.zip", size_bytes: 204800, sha256: "y", url: "/api/exports/e2", created_at: "2026-11-14T10:00:00Z" },
  ],
};

const stub = (routes: Record<string, unknown>) =>
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const hit = Object.entries(routes).find(([k]) => url.endsWith(k));
      if (!hit) throw new Error(`unexpected ${url}`);
      return Response.json(hit[1]);
    }),
  );

afterEach(() => vi.unstubAllGlobals());

describe("ResultsView", () => {
  it("shows the described player and the downloads, best file first", async () => {
    stub({ [`${P}/schedule`]: standard, [`${P}/schedule?mode=extended`]: { available: false }, [`${P}/transcript`]: transcript, [`${P}/exports`]: exports });
    const { container } = render(<ResultsView projectId={P} title="Week 1" />);
    expect(await screen.findByLabelText("Week 1, with audio descriptions")).toHaveAttribute("src", `/api/projects/${P}/video`);
    const files = within(screen.getByRole("list", { name: "Export files" })).getAllByRole("listitem");
    expect(files[0]).toHaveTextContent("Everything (zip)seehere-export.zip · 200 KB");
    expect(within(files[0]).getByRole("link", { name: "Download Everything (zip)" })).toHaveAttribute("href", "/api/exports/e2");
    expect(screen.getByText(/not a WCAG conformance certification/)).toBeInTheDocument();
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });

  it("explains when there is nothing to play yet", async () => {
    stub({ [`${P}/schedule`]: { available: false }, [`${P}/schedule?mode=extended`]: { available: false }, [`${P}/transcript`]: transcript, [`${P}/exports`]: { available: false, files: [] } });
    render(<ResultsView projectId={P} title="Week 1" />);
    expect(await screen.findByText("No results yet")).toBeInTheDocument();
  });
});

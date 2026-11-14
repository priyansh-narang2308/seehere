import { render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Exports, Report, Schedule, Transcript } from "@/lib/api";
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

const item = { kind: "text_block" as const, t_end_s: 9, cue_id: "c9", text: "On screen: “Q3 risks”.", verification_state: "needs_review" as const, review_status: "pending" as const, pause_s: null };
const report: Report = {
  available: true,
  summary: { visual_units: 3, described: 1, described_extended: 0, said_aloud: 1, repeat: 0, skipped: 0, held_for_review: 1, rejected: 0, not_scheduled: 0, uncovered: 1, descriptions: 2 },
  verification: { verified_text_match: 1, corroborated: 0, uncertain: 0, needs_review: 1 },
  checks: { pass: 2, fail: 1, inconclusive: 0 },
  review: { pending: 2, approved: 0, rejected: 0 },
  timing: { standard: { solver: "cp_sat", round: 2, check: { status: "fits" } }, extended: { round: 2, budget_s: 1.2, paused_s: 0.4, extended_duration_s: 15.4 } },
  items: [{ ...item, visual_unit_id: "u9", label: "Q3 risks", t_start_s: 7, coverage: 0, outcome: "held_for_review", reason: "a claim is not supported by the evidence" }],
  notice: "Evidence, not complete fact-checking.",
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
    stub({ [`${P}/schedule`]: standard, [`${P}/schedule?mode=extended`]: { available: false }, [`${P}/transcript`]: transcript, [`${P}/exports`]: exports, [`${P}/report`]: report });
    const { container } = render(<ResultsView projectId={P} title="Week 1" />);
    expect(await screen.findByLabelText("Week 1, with audio descriptions")).toHaveAttribute("src", `/api/projects/${P}/video`);
    const files = within(screen.getByRole("list", { name: "Export files" })).getAllByRole("listitem");
    expect(files[0]).toHaveTextContent("Everything (zip)seehere-export.zip · 200 KB");
    expect(within(files[0]).getByRole("link", { name: "Download Everything (zip)" })).toHaveAttribute("href", "/api/exports/e2");
    expect(screen.getByText(/not a WCAG conformance certification/)).toBeInTheDocument();

    const coverage = within(screen.getByRole("region", { name: "Coverage and verification" }));
    expect(coverage.getByText("3 visual items found on screen; 1 not described to the listener.")).toBeInTheDocument();
    expect(coverage.getByRole("rowheader", { name: "Not described: waiting for review" }).nextSibling).toHaveTextContent("1");
    expect(coverage.getByText(/Standard: CP-SAT schedule, round 2; audio fits every slot./)).toBeInTheDocument();
    expect(within(coverage.getByRole("list", { name: "Uncovered visuals" })).getByRole("listitem")).toHaveTextContent(
      "Q3 risks (Not described: waiting for review: a claim is not supported by the evidence)",
    );
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });

  it("explains when there is nothing to play yet", async () => {
    stub({ [`${P}/schedule`]: { available: false }, [`${P}/schedule?mode=extended`]: { available: false }, [`${P}/transcript`]: transcript, [`${P}/exports`]: { available: false, files: [] }, [`${P}/report`]: { available: false } });
    render(<ResultsView projectId={P} title="Week 1" />);
    expect(await screen.findByText("No results yet")).toBeInTheDocument();
  });
});

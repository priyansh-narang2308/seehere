"use client";

import { CalendarClock, Pause } from "lucide-react";
import { useState } from "react";
import type { Schedule, SolverResult } from "@/lib/api";

/** m:ss.t, truncated (not rounded) so 7.89 s reads 0:07.8. */
const at = (s: number) => {
  const tenths = Math.floor(s * 10);
  return `${Math.floor(tenths / 600)}:${String(Math.floor(tenths / 10) % 60).padStart(2, "0")}.${tenths % 10}`;
};
const share = (r: SolverResult) => (r.priority_placed_share === null ? "–" : `${Math.round(r.priority_placed_share * 100)}%`);

type Mode = "standard" | "extended";

/**
 * Where each description plays. Standard: only inside pauses in speech. Extended: the video may
 * also pause, within a budget, and each pause says why.
 */
export function ScheduleView({ standard, extended, durationS }: { standard: Schedule; extended: Schedule | null; durationS: number | null }) {
  const [mode, setMode] = useState<Mode>("standard");
  const schedule = mode === "extended" && extended ? extended : standard;
  const total = durationS ?? Math.max(1, ...schedule.windows.map((w) => w.end_s));
  const pct = (s: number) => `${(Math.min(s, total) / total) * 100}%`;
  const cmp = standard.comparison;
  const voiced = schedule.placements.every((p) => p.audio_s !== null);
  return (
    <div className="space-y-3 border-t border-border px-5 py-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-1.5 text-sm font-medium text-ink">
          <CalendarClock aria-hidden="true" className="size-4" /> Schedule
        </h3>
        {extended && (
          <div role="group" aria-label="Description mode" className="flex rounded-md border border-border text-xs">
            {(["standard", "extended"] as const).map((m) => (
              <button
                key={m}
                type="button"
                aria-pressed={mode === m}
                onClick={() => setMode(m)}
                className={`px-2.5 py-1 capitalize first:rounded-l-md last:rounded-r-md ${mode === m ? "bg-accent text-white" : "text-ink-2 hover:bg-sunken"}`}
              >
                {m}
              </button>
            ))}
          </div>
        )}
      </div>
      {schedule.status !== "succeeded" ? (
        <p role="alert" className="text-sm text-danger">
          The schedule failed its overlap check and is not used.
        </p>
      ) : (
        <>
          <p className="text-sm text-muted">
            {schedule.placements.length} of {schedule.placements.length + schedule.not_placed.length} descriptions{" "}
            {schedule.mode === "extended"
              ? `are voiced; the video pauses ${schedule.paused_s ?? 0} s in total (budget ${schedule.pause_budget_s ?? 0} s).`
              : "fit into pauses in speech, with no overlap."}{" "}
            {voiced ? "Lengths are measured from the generated voice." : "Timings are estimates until the voice is generated."}
          </p>
          {schedule.mode === "standard" && cmp && (
            <p className="text-sm text-muted">
              Solver: {schedule.solver === "cp_sat" ? "CP-SAT" : "greedy"}. On the same inputs, greedy placed {cmp.greedy.placed} (
              {share(cmp.greedy)} of priority) and CP-SAT placed {cmp.cp_sat.placed} ({share(cmp.cp_sat)}).
            </p>
          )}
          {/* Visual summary; the lists below carry the same information as text. */}
          <div aria-hidden="true" className="relative h-6 overflow-hidden rounded bg-sunken">
            {schedule.windows.map((w, i) => (
              <span key={i} className="absolute inset-y-0 bg-success-soft" style={{ left: pct(w.start_s), width: `calc(${pct(w.end_s)} - ${pct(w.start_s)})` }} />
            ))}
            {schedule.placements.map((p) => (
              <span
                key={p.cue_id}
                className={`absolute inset-y-1 rounded-sm ${p.pause_s > 0 ? "bg-warning" : "bg-accent"}`}
                style={{ left: pct(p.start_s), width: `calc(${pct(p.end_s)} - ${pct(p.start_s)})` }}
              />
            ))}
          </div>
          <p aria-hidden="true" className="text-xs text-muted">
            Grey: speech. Green: pauses. Blue: descriptions.{schedule.mode === "extended" ? " Amber: the video pauses." : ""}
          </p>
          {schedule.placements.length > 0 && (
            <ol aria-label="Scheduled descriptions" className="space-y-2 text-sm">
              {schedule.placements.map((p) => (
                <li key={p.cue_id} className="flex gap-3">
                  <span className="w-28 shrink-0 font-mono text-xs leading-5 text-muted">
                    <time dateTime={`PT${p.start_s}S`}>{at(p.start_s)}</time>–<time dateTime={`PT${p.end_s}S`}>{at(p.end_s)}</time>
                  </span>
                  <span className="min-w-0 space-y-1 text-ink-2">
                    <span className="block">
                      {p.text} <span className="text-xs text-muted">({p.variant}{p.audio_s !== null ? `, ${p.audio_s.toFixed(1)} s spoken` : ""})</span>
                    </span>
                    {p.pause_s > 0 && p.pause_reason && (
                      <span className="flex items-start gap-1 text-xs text-muted">
                        <Pause aria-hidden="true" className="mt-0.5 size-3 shrink-0" />
                        <span>
                          Video pauses {p.pause_s.toFixed(1)} s: {p.pause_reason}
                        </span>
                      </span>
                    )}
                    {p.audio_url && (
                      <audio controls preload="none" src={p.audio_url} aria-label={`Play: ${p.text}`} className="h-8 max-w-full" />
                    )}
                  </span>
                </li>
              ))}
            </ol>
          )}
          {schedule.not_placed.length > 0 && (
            <>
              <h4 className="text-sm font-medium text-ink">Not voiced</h4>
              <ul aria-label="Descriptions not voiced" className="space-y-1 text-sm">
                {schedule.not_placed.map((n) => (
                  <li key={n.cue_id} className="text-ink-2">
                    {n.text} <span className="text-muted">— {n.reason}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </div>
  );
}

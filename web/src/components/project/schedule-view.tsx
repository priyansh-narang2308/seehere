import { CalendarClock } from "lucide-react";
import type { Schedule } from "@/lib/api";

/** m:ss.t, truncated (not rounded) so 7.89 s reads 0:07.8. */
const at = (s: number) => {
  const tenths = Math.floor(s * 10);
  return `${Math.floor(tenths / 600)}:${String(Math.floor(tenths / 10) % 60).padStart(2, "0")}.${tenths % 10}`;
};

/** Where each description plays: only inside pauses in speech, never over the speaker. */
export function ScheduleView({ schedule, durationS }: { schedule: Schedule; durationS: number | null }) {
  const total = durationS ?? Math.max(1, ...schedule.windows.map((w) => w.end_s));
  const pct = (s: number) => `${(Math.min(s, total) / total) * 100}%`;
  return (
    <div className="space-y-3 border-t border-border px-5 py-4">
      <h3 className="flex items-center gap-1.5 text-sm font-medium text-ink">
        <CalendarClock aria-hidden="true" className="size-4" /> Schedule
      </h3>
      {schedule.status !== "succeeded" ? (
        <p role="alert" className="text-sm text-danger">
          The schedule failed its overlap check and is not used.
        </p>
      ) : (
        <>
          <p className="text-sm text-muted">
            {schedule.placements.length} of {schedule.placements.length + schedule.not_placed.length} descriptions fit
            into pauses in speech, with no overlap. Timings are estimates until the voice is generated.
          </p>
          {/* Visual summary; the lists below carry the same information as text. */}
          <div aria-hidden="true" className="relative h-6 overflow-hidden rounded bg-sunken">
            {schedule.windows.map((w, i) => (
              <span key={i} className="absolute inset-y-0 bg-success-soft" style={{ left: pct(w.start_s), width: `calc(${pct(w.end_s)} - ${pct(w.start_s)})` }} />
            ))}
            {schedule.placements.map((p) => (
              <span key={p.cue_id} className="absolute inset-y-1 rounded-sm bg-accent" style={{ left: pct(p.start_s), width: `calc(${pct(p.end_s)} - ${pct(p.start_s)})` }} />
            ))}
          </div>
          <p aria-hidden="true" className="text-xs text-muted">
            Grey: speech. Green: pauses. Blue: descriptions.
          </p>
          {schedule.placements.length > 0 && (
            <ol aria-label="Scheduled descriptions" className="space-y-2 text-sm">
              {schedule.placements.map((p) => (
                <li key={p.cue_id} className="flex gap-3">
                  <span className="w-28 shrink-0 font-mono text-xs leading-5 text-muted">
                    <time dateTime={`PT${p.start_s}S`}>{at(p.start_s)}</time>–<time dateTime={`PT${p.end_s}S`}>{at(p.end_s)}</time>
                  </span>
                  <span className="text-ink-2">
                    {p.text} <span className="text-xs text-muted">({p.variant})</span>
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

import { VERIFICATION_STATES } from "@/components/ui/verification-badge";
import { formatDuration, type Report, type ReportOutcome } from "@/lib/api";

export const OUTCOME_LABEL: Record<ReportOutcome, string> = {
  described: "Described",
  described_extended: "Described in extended mode",
  said_aloud: "Said aloud by the speaker",
  repeat: "Already described on this frame",
  skipped: "Not described: no room",
  held_for_review: "Not described: waiting for review",
  rejected: "Not described: rejected",
  not_scheduled: "Not described: not scheduled yet",
};

const UNCOVERED = new Set<ReportOutcome>(["skipped", "held_for_review", "rejected", "not_scheduled"]);

/** Coverage and verification report: what happened to every visual on screen (Task 28). */
export function ReportView({ report }: { report: Extract<Report, { available: true }> }) {
  const { summary, verification, timing } = report;
  const outcomes = (Object.keys(OUTCOME_LABEL) as ReportOutcome[]).filter((k) => summary[k] > 0);
  const uncovered = report.items.filter((i) => UNCOVERED.has(i.outcome));
  const fit = timing.standard?.check?.status;
  return (
    <section aria-labelledby="report" className="space-y-4">
      <div>
        <h2 id="report" className="text-lg font-semibold tracking-tight text-ink">
          Coverage and verification
        </h2>
        <p className="mt-1 text-sm text-muted">
          {summary.visual_units} visual items found on screen; {summary.uncovered} not described to the listener.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <table className="text-sm">
          <caption className="mb-1 text-left text-xs font-medium text-ink-2">Outcomes</caption>
          <tbody>
            {outcomes.map((k) => (
              <tr key={k}>
                <th scope="row" className="py-0.5 pr-3 text-left font-normal text-ink-2">
                  {OUTCOME_LABEL[k]}
                </th>
                <td className="font-mono text-ink">{summary[k]}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <table className="text-sm">
          <caption className="mb-1 text-left text-xs font-medium text-ink-2">Descriptions by verification state</caption>
          <tbody>
            {(Object.keys(VERIFICATION_STATES) as (keyof typeof VERIFICATION_STATES)[]).map((k) => (
              <tr key={k}>
                <th scope="row" className="py-0.5 pr-3 text-left font-normal text-ink-2">
                  {VERIFICATION_STATES[k].label}
                </th>
                <td className="font-mono text-ink">{verification[k]}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <dl className="text-sm">
          <dt className="text-xs font-medium text-ink-2">Timing</dt>
          <dd className="text-ink">
            {timing.standard
              ? `Standard: ${timing.standard.solver === "cp_sat" ? "CP-SAT" : "greedy"} schedule, round ${timing.standard.round}; audio ${fit === "fits" ? "fits every slot" : (fit ?? "not checked yet")}.`
              : "No schedule yet."}
          </dd>
          {timing.extended && (
            <dd className="text-ink">
              Extended: {(timing.extended.paused_s ?? 0).toFixed(1)} s of pauses within a {(timing.extended.budget_s ?? 0).toFixed(1)} s budget.
            </dd>
          )}
          <dt className="mt-2 text-xs font-medium text-ink-2">Review</dt>
          <dd className="text-ink">
            {report.review.approved} approved, {report.review.rejected} rejected, {report.review.pending} not reviewed.
          </dd>
        </dl>
      </div>
      {uncovered.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-ink">Not described to the listener</h3>
          <ul aria-label="Uncovered visuals" className="mt-1 space-y-1 text-sm">
            {uncovered.map((i) => (
              <li key={i.visual_unit_id} className="flex gap-3">
                <span className="w-12 shrink-0 font-mono text-xs leading-5 text-muted">{formatDuration(i.t_start_s)}</span>
                <span className="min-w-0">
                  <span className="text-ink">{i.label}</span>{" "}
                  <span className="text-ink-2">
                    ({OUTCOME_LABEL[i.outcome]}
                    {i.reason ? `: ${i.reason}` : ""})
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="text-xs text-muted">{report.notice}</p>
    </section>
  );
}

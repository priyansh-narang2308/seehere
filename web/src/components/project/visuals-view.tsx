import { Eye } from "lucide-react";
import { formatDuration, type VisualKind, type Visuals } from "@/lib/api";

const KIND: Record<VisualKind, string> = {
  chart: "Chart",
  diagram: "Diagram",
  table: "Table",
  equation: "Equation",
  text_block: "Text",
  image: "Image",
  other: "Other",
};

/** What is on screen, most in need of description first: what was shown but not said aloud. */
export function VisualsView({ visuals }: { visuals: Visuals }) {
  const { units, scored } = visuals;
  return (
    <div className="space-y-3 border-t border-border px-5 py-4">
      <h3 className="flex items-center gap-1.5 text-sm font-medium text-ink">
        <Eye aria-hidden="true" className="size-4" /> Seen versus said
      </h3>
      {units.length === 0 ? (
        <p className="text-sm text-muted">No visual content was found on the keyframes.</p>
      ) : (
        <>
          <p className="text-sm text-muted">
            {scored
              ? "Each item on screen is compared with what the speaker said while it was shown. Items mostly not said aloud come first."
              : "Waiting for the transcript to compare what is shown with what is said."}
          </p>
          <ol aria-label="Visual content by priority" className="max-h-96 space-y-3 overflow-y-auto text-sm" tabIndex={0}>
            {units.map((u) => (
              <li key={u.id} className="flex gap-3">
                <span className="w-24 shrink-0 font-mono text-xs leading-5 text-muted">
                  <time dateTime={`PT${u.t_start_s}S`}>{formatDuration(u.t_start_s)}</time>–
                  <time dateTime={`PT${u.t_end_s}S`}>{formatDuration(u.t_end_s)}</time>
                </span>
                <div className="min-w-0 space-y-1">
                  <p className="text-ink">
                    <span className="rounded bg-sunken px-1.5 py-0.5 text-xs text-ink-2">{KIND[u.kind]}</span>{" "}
                    {u.label}
                  </p>
                  {u.coverage !== null && (
                    <p className="text-xs text-ink-2">
                      <span className="font-medium">{Math.round(u.coverage * 100)}% said aloud</span>
                      {u.unsaid.length > 0 && <> · not said: {u.unsaid.join(", ")}</>}
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  );
}

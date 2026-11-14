import { MousePointerClick } from "lucide-react";
import { formatDuration, type References } from "@/lib/api";

/** Spoken pointers ("this line here"): what each was linked to, or why it needs a person. */
export function ReferencesView({ references }: { references: References["references"] }) {
  return (
    <div className="space-y-3 border-t border-border px-5 py-4">
      <h3 className="flex items-center gap-1.5 text-sm font-medium text-ink">
        <MousePointerClick aria-hidden="true" className="size-4" /> Spoken references
      </h3>
      {references.length === 0 ? (
        <p className="text-sm text-muted">The speaker did not point at anything on screen.</p>
      ) : (
        <ol aria-label="Spoken references" className="space-y-2 text-sm">
          {references.map((r, i) => (
            <li key={i} className="flex gap-3">
              <time className="w-12 shrink-0 font-mono text-xs leading-5 text-muted" dateTime={`PT${r.t_s}S`}>
                {formatDuration(r.t_s)}
              </time>
              <span className="text-ink-2">
                <span className="text-ink">“{r.phrase}”</span>{" "}
                {r.status === "linked" ? (
                  <>
                    points at “{r.label}” ({Math.round(r.confidence * 100)}% confidence)
                  </>
                ) : r.status === "ambiguous" ? (
                  <span className="font-medium text-warning">needs review: more than one item fits</span>
                ) : (
                  <span className="text-muted">nothing on screen to point at</span>
                )}
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

import { ScanText } from "lucide-react";
import { formatDuration, type OcrResult } from "@/lib/api";

const LOW_CONFIDENCE = 0.6;

/** Text read from each keyframe, in reading order, with low-confidence lines marked. */
export function OcrView({ ocr }: { ocr: OcrResult }) {
  const withText = ocr.keyframes.filter((k) => k.regions.length > 0);
  return (
    <div className="space-y-3 border-t border-border px-5 py-4">
      <h3 className="flex items-center gap-1.5 text-sm font-medium text-ink">
        <ScanText aria-hidden="true" className="size-4" /> On-screen text
      </h3>
      {withText.length === 0 ? (
        <p className="text-sm text-muted">No text was found on the keyframes.</p>
      ) : (
        <>
          <p className="text-sm text-muted">
            Read by OCR from {withText.length} of {ocr.keyframes.length} keyframes. OCR can misread characters, so this
            is evidence to check, not verified fact.
          </p>
          <ol aria-label="Text by keyframe" className="space-y-3 text-sm">
            {withText.map((k) => (
              <li key={k.frame_id} className="flex gap-3">
                <time className="w-12 shrink-0 font-mono text-xs leading-5 text-muted" dateTime={`PT${k.t_s}S`}>
                  {formatDuration(k.t_s)}
                </time>
                <ul className="space-y-0.5">
                  {k.regions.map((r, i) => (
                    <li key={i} className="text-ink-2">
                      {r.text}
                      {r.confidence < LOW_CONFIDENCE && <span className="ml-1.5 text-xs text-warning">(low confidence)</span>}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  );
}

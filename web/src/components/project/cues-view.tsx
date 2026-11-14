"use client";

import { MessageSquareText } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { API_BASE, formatDuration, getJson, type Cue, type CueLedger, type VerificationState } from "@/lib/api";

const STATE: Record<VerificationState, string> = {
  verified_text_match: "Verified text match",
  corroborated: "Corroborated",
  uncertain: "Uncertain",
  needs_review: "Needs review",
};

/** Description cues in time order, each with its wordings and, on request, its evidence. */
export function CuesView({ cues }: { cues: Cue[] }) {
  return (
    <div className="space-y-3 border-t border-border px-5 py-4">
      <h3 className="flex items-center gap-1.5 text-sm font-medium text-ink">
        <MessageSquareText aria-hidden="true" className="size-4" /> Descriptions
      </h3>
      {cues.length === 0 ? (
        <p className="text-sm text-muted">Everything on screen was said aloud, so nothing needs describing.</p>
      ) : (
        <>
          <p className="text-sm text-muted">
            Drafts written only from what was read on screen. Each needs review until its claims are checked.
          </p>
          <ol aria-label="Descriptions" className="space-y-4 text-sm">
            {cues.map((c) => (
              <CueItem key={c.id} cue={c} />
            ))}
          </ol>
        </>
      )}
    </div>
  );
}

function CueItem({ cue }: { cue: Cue }) {
  const [ledger, setLedger] = useState<CueLedger | null>(null);
  const [open, setOpen] = useState(false);
  const [failed, setFailed] = useState(false);
  const panelId = `evidence-${cue.id}`;

  async function toggle() {
    setOpen(!open);
    if (ledger || open) return;
    try {
      setLedger(await getJson<CueLedger>(`/api/cues/${cue.id}/evidence`));
    } catch {
      setFailed(true);
    }
  }

  return (
    <li className="flex gap-3">
      <time className="w-12 shrink-0 font-mono text-xs leading-5 text-muted" dateTime={`PT${cue.anchor_t_s}S`}>
        {formatDuration(cue.anchor_t_s)}
      </time>
      <div className="min-w-0 flex-1 space-y-1.5">
        <p className="text-ink">{cue.text_short}</p>
        {cue.text_long && <p className="text-ink-2">Long: {cue.text_long}</p>}
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded bg-sunken px-1.5 py-0.5 text-xs text-ink-2">{STATE[cue.verification_state]}</span>
          <Button size="sm" variant="secondary" aria-expanded={open} aria-controls={panelId} onClick={toggle}>
            {open ? "Hide evidence" : "Show evidence"}
          </Button>
        </div>
        {open && (
          <div id={panelId}>
            {failed && <p role="alert" className="text-danger">The evidence could not be loaded.</p>}
            {!failed && !ledger && <p className="text-muted">Loading evidence…</p>}
            {ledger && <Evidence ledger={ledger} />}
          </div>
        )}
      </div>
    </li>
  );
}

function Evidence({ ledger }: { ledger: CueLedger }) {
  const frame = ledger.evidence.find((e) => e.frame)?.frame;
  const unit = ledger.evidence.find((e) => e.visual_unit)?.visual_unit;
  return (
    <div className="space-y-2 rounded-md border border-border bg-surface-muted p-3">
      {frame && (
        <figure className="w-64 max-w-full">
          {/* The overlay is positioned against the image alone, not the caption. */}
          <div className="relative">
            {/* eslint-disable-next-line @next/next/no-img-element -- frames come from the API */}
            <img src={`${API_BASE}${frame.image_url}`} alt={`Keyframe at ${formatDuration(frame.t_s)}`} className="block w-full rounded border border-border" />
            {unit?.box && (
              <span
                aria-hidden="true"
                className="absolute border-2 border-accent"
                style={{ left: `${unit.box.x * 100}%`, top: `${unit.box.y * 100}%`, width: `${unit.box.w * 100}%`, height: `${unit.box.h * 100}%` }}
              />
            )}
          </div>
          <figcaption className="text-xs text-muted">The outlined region is what this description is about.</figcaption>
        </figure>
      )}
      <ul aria-label="Evidence" className="space-y-1 text-xs text-ink-2">
        {ledger.evidence.map((e, i) => (
          <li key={i}>
            {e.ocr_region && <>Read on screen: “{e.ocr_region.text}” ({Math.round(e.ocr_region.confidence * 100)}% OCR confidence)</>}
            {e.slide && <>Deck page {e.slide.page}: “{e.slide.text.split("\n")[0]}”</>}
            {e.transcript && (
              <>
                {e.note === "speech while shown" ? "Said while shown" : "Pointed at"} ({formatDuration(e.transcript.start_s)}): “
                {e.transcript.text}”
              </>
            )}
            {e.visual_unit && (
              <>
                On screen {formatDuration(e.visual_unit.t_start_s)}–{formatDuration(e.visual_unit.t_end_s)}
                {e.visual_unit.coverage !== null && <>, {Math.round(e.visual_unit.coverage * 100)}% said aloud</>}
              </>
            )}
            {e.frame && <>Keyframe at {formatDuration(e.frame.t_s)}</>}
          </li>
        ))}
      </ul>
    </div>
  );
}

"use client";

import { MessageSquareText } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { VERIFICATION_STATES, VerificationBadge } from "@/components/ui/verification-badge";
import {
  API_BASE,
  ApiError,
  formatDuration,
  getJson,
  reviewCue,
  type Cue,
  type CueLedger,
  type ReviewAction,
} from "@/lib/api";

const CHECK_RESULT = { pass: "Found", fail: "Not found", inconclusive: "Unclear" } as const;
const CHECK_NAME = { quote_match: "quote", number_match: "number", description_support: "statement" } as const;
const REVIEW_LABEL = { pending: "Not reviewed", approved: "Approved", rejected: "Rejected" } as const;
const ACTION_LABEL = { approve: "Approved", reject: "Rejected", edit: "Edited", regenerate: "Regenerated" } as const;
const MAX_TEXT = 500;

/** Description cues in time order, each with its wordings, review controls and evidence. */
export function CuesView({ cues, onChanged }: { cues: Cue[]; onChanged?: () => void }) {
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
            Drafts written only from what was read on screen. Each quote and number is checked against that
            evidence. Descriptions that need review are not voiced until you approve them.
          </p>
          <ol aria-label="Descriptions" className="space-y-4 text-sm">
            {cues.map((c) => (
              <CueItem key={c.id} cue={c} onChanged={onChanged} />
            ))}
          </ol>
        </>
      )}
    </div>
  );
}

function CueItem({ cue: initial, onChanged }: { cue: Cue; onChanged?: () => void }) {
  const [ledger, setLedger] = useState<CueLedger | null>(null);
  const [open, setOpen] = useState(false);
  const [failed, setFailed] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState<ReviewAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const cue = ledger?.cue ?? initial;
  const panelId = `evidence-${cue.id}`;
  const editId = `edit-${cue.id}`;

  async function toggle() {
    setOpen(!open);
    if (ledger || open) return;
    try {
      setLedger(await getJson<CueLedger>(`/api/cues/${cue.id}/evidence`));
    } catch {
      setFailed(true);
    }
  }

  async function act(action: ReviewAction, text?: string) {
    setBusy(action);
    setError(null);
    try {
      const next = await reviewCue(cue.id, text === undefined ? { action } : { action, text });
      setLedger(next);
      setFailed(false);
      setEditing(false);
      setStatus(`${ACTION_LABEL[action]}. The schedule is being updated.`);
      onChanged?.();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The review could not be saved.");
    } finally {
      setBusy(null);
    }
  }

  function startEdit() {
    setDraft(cue.text_short);
    setEditing(true);
    setError(null);
  }

  const held = cue.verification_state === "needs_review" && cue.review_status !== "approved";
  const rejected = cue.review_status === "rejected";

  return (
    <li className="flex gap-3">
      <time className="w-12 shrink-0 font-mono text-xs leading-5 text-muted" dateTime={`PT${cue.anchor_t_s}S`}>
        {formatDuration(cue.anchor_t_s)}
      </time>
      <div className="min-w-0 flex-1 space-y-1.5">
        <p className={rejected ? "text-muted line-through" : "text-ink"}>{cue.text_short}</p>
        {cue.text_long && !rejected && <p className="text-ink-2">Long: {cue.text_long}</p>}
        <div className="flex flex-wrap items-center gap-2">
          <VerificationBadge state={cue.verification_state} />
          <span className="text-xs text-muted">
            Review: <span className="font-medium text-ink-2">{REVIEW_LABEL[cue.review_status]}</span>
            {rejected ? " · not voiced" : held ? " · held until approved" : ""}
          </span>
        </div>

        {editing ? (
          <form
            className="space-y-1.5"
            onSubmit={(e) => {
              e.preventDefault();
              void act("edit", draft.trim());
            }}
          >
            <label htmlFor={editId} className="block text-xs font-medium text-ink-2">
              Corrected description
            </label>
            <textarea
              id={editId}
              value={draft}
              maxLength={MAX_TEXT}
              rows={3}
              onChange={(e) => setDraft(e.target.value)}
              className="w-full rounded-md border border-border bg-surface p-2 text-sm text-ink"
            />
            <p className="text-xs text-muted">
              Saving approves your wording. It is still checked against the evidence and the result is shown.
            </p>
            <div className="flex gap-2">
              <Button size="sm" type="submit" disabled={busy !== null || draft.trim() === ""}>
                {busy === "edit" ? "Saving…" : "Save and approve"}
              </Button>
              <Button size="sm" variant="secondary" type="button" onClick={() => setEditing(false)}>
                Cancel
              </Button>
            </div>
          </form>
        ) : (
          <div role="group" aria-label="Review" className="flex flex-wrap items-center gap-2">
            {cue.review_status !== "approved" && (
              <Button size="sm" disabled={busy !== null} onClick={() => act("approve")}>
                {busy === "approve" ? "Approving…" : "Approve"}
              </Button>
            )}
            {!rejected && (
              <Button size="sm" variant="secondary" disabled={busy !== null} onClick={() => act("reject")}>
                {busy === "reject" ? "Rejecting…" : "Reject"}
              </Button>
            )}
            <Button size="sm" variant="secondary" disabled={busy !== null} onClick={startEdit}>
              Edit
            </Button>
            <Button size="sm" variant="secondary" disabled={busy !== null} onClick={() => act("regenerate")}>
              {busy === "regenerate" ? "Regenerating…" : "Regenerate"}
            </Button>
            <Button size="sm" variant="secondary" aria-expanded={open} aria-controls={panelId} onClick={toggle}>
              {open ? "Hide evidence" : "Show evidence"}
            </Button>
          </div>
        )}
        {error && (
          <p role="alert" className="text-danger">
            {error}
          </p>
        )}
        <p role="status" className="text-xs text-muted">
          {status}
        </p>
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
      <p className="text-xs text-ink-2">
        Verification: <span className="font-medium">{VERIFICATION_STATES[ledger.cue.verification_state].label}</span>.{" "}
        {VERIFICATION_STATES[ledger.cue.verification_state].help} OCR matching is evidence, not full fact-checking.
      </p>
      {ledger.checks.length > 0 && (
        <ul aria-label="Checks" className="space-y-1 text-xs text-ink-2">
          {ledger.checks.map((c, i) => (
            <li key={i}>
              <span className={c.result === "fail" ? "font-medium text-danger" : c.result === "pass" ? "text-success" : "text-warning"}>
                {CHECK_RESULT[c.result]}
              </span>{" "}
              {CHECK_NAME[c.check]} “{c.claim}”
              {c.detail.reason ? `: ${c.detail.reason}` : c.detail.source ? ` (${c.detail.source === "ocr" ? "read on screen" : c.detail.source})` : ""}
            </li>
          ))}
        </ul>
      )}
      {unit?.unsaid && unit.unsaid.length > 0 && (
        <div className="text-xs text-ink-2">
          <p className="font-medium">On screen but not said aloud</p>
          <ul aria-label="Not said aloud" className="list-disc pl-4">
            {unit.unsaid.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </div>
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
      {ledger.decisions.length > 0 && (
        <div className="text-xs text-ink-2">
          <p className="font-medium">Review history</p>
          <ol aria-label="Review history" className="space-y-0.5">
            {ledger.decisions.map((d, i) => (
              <li key={i}>
                <time dateTime={d.created_at}>{new Date(d.created_at).toLocaleString()}</time>: {ACTION_LABEL[d.action]}
                {d.new_text && d.new_text !== d.previous_text && <> to “{d.new_text}”</>}
                {d.note && <> ({d.note})</>}
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

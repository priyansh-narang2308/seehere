"use client";

import { Presentation, Upload } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { ApiError, formatDuration, getJson, uploadDeck, type Deck } from "@/lib/api";

/**
 * Optional slide deck: add a PDF or PPTX, then see which keyframe each page was matched to.
 * `version` changes whenever the deck job finishes, so the pages are reloaded.
 */
export function DeckSection({
  projectId,
  version,
  onUploaded,
}: {
  projectId: string;
  version: string;
  onUploaded: () => void;
}) {
  const [deck, setDeck] = useState<Deck | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const hintId = useId();

  useEffect(() => {
    const controller = new AbortController();
    getJson<Deck>(`/api/projects/${projectId}/deck`, { signal: controller.signal })
      .then(setDeck)
      .catch(() => {});
    return () => controller.abort();
  }, [projectId, version]);

  async function upload(file: File) {
    setBusy(true);
    setError(null);
    try {
      setDeck(await uploadDeck(projectId, file));
      onUploaded();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The deck could not be uploaded.");
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  const matched = deck?.pages.filter((p) => p.t_s !== null).length ?? 0;
  return (
    <div className="space-y-3 border-t border-border px-5 py-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="flex items-center gap-1.5 text-sm font-medium text-ink">
          <Presentation aria-hidden="true" className="size-4" /> Slide deck <span className="font-normal text-muted">(optional)</span>
        </h3>
        <input
          ref={input}
          type="file"
          accept=".pdf,.pptx"
          className="sr-only"
          aria-label="Slide deck file"
          aria-describedby={hintId}
          onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
        />
        <Button size="sm" variant="secondary" loading={busy} onClick={() => input.current?.click()}>
          <Upload aria-hidden="true" /> {deck?.available ? "Replace deck" : "Add deck"}
        </Button>
      </div>
      <p id={hintId} className="text-sm text-muted">
        A PDF or PPTX of the slides gives exact slide text. Each page is matched to the moment it appears.
      </p>
      {error && (
        <p role="alert" className="rounded-md border border-danger-line bg-danger-soft px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}
      {deck?.available && !deck.ingested && <p className="text-sm text-muted">Reading {deck.filename}…</p>}
      {deck?.available && deck.ingested && (
        <>
          <p className="text-sm text-ink-2">
            <span className="font-medium text-ink">{deck.filename}</span>: {deck.pages.length}{" "}
            {deck.pages.length === 1 ? "page" : "pages"}, {matched} matched to the video.
          </p>
          <ol aria-label="Deck pages" className="max-h-72 space-y-2 overflow-y-auto text-sm" tabIndex={0}>
            {deck.pages.map((p) => (
              <li key={p.page} className="flex gap-3">
                <span className="w-16 shrink-0 font-mono text-xs leading-5 text-muted">Page {p.page}</span>
                <span className="w-24 shrink-0 text-xs leading-5">
                  {p.t_s !== null ? (
                    <time className="font-mono text-ink-2" dateTime={`PT${p.t_s}S`}>
                      at {formatDuration(p.t_s)}
                    </time>
                  ) : (
                    <span className="text-muted">Not matched</span>
                  )}
                </span>
                <span className="line-clamp-2 text-ink-2">{p.text.split("\n")[0] || "(no text)"}</span>
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  );
}

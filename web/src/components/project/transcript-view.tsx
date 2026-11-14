import { Captions } from "lucide-react";
import { formatDuration, type Transcript } from "@/lib/api";

const LANGUAGES: Record<string, string> = { en: "English" };

/** The timed transcript: one row per recognized segment, with its start time. */
export function TranscriptView({ transcript }: { transcript: Transcript }) {
  const { segments, word_count, language, provider } = transcript;
  const model = provider?.replace(/^faster-whisper:/, "Whisper ");
  return (
    <div className="space-y-3 border-t border-border px-5 py-4">
      <h3 className="flex items-center gap-1.5 text-sm font-medium text-ink">
        <Captions aria-hidden="true" className="size-4" /> Transcript
      </h3>
      {segments.length === 0 ? (
        <p className="text-sm text-muted">No speech was detected in this video.</p>
      ) : (
        <>
          <p className="text-sm text-muted">
            {word_count} {word_count === 1 ? "word" : "words"} with timings
            {language && `, ${LANGUAGES[language] ?? language}`}
            {model && `, recognized locally by ${model}`}. Machine transcription can contain errors.
          </p>
          {/* Scrollable, so it must be focusable for keyboard users. */}
          <ol
            aria-label="Transcript segments"
            tabIndex={0}
            className="max-h-80 space-y-2 overflow-y-auto rounded-md border border-border bg-sunken p-3 text-sm"
          >
            {segments.map((s) => (
              <li key={`${s.start_s}-${s.end_s}`} className="flex gap-3">
                <time className="w-12 shrink-0 font-mono text-xs leading-5 text-muted" dateTime={`PT${s.start_s}S`}>
                  {formatDuration(s.start_s)}
                </time>
                <span className="text-ink-2">{s.text}</span>
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  );
}

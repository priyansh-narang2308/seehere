"use client";

import { AudioLines, Captions } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import {
  activeEntry,
  clock,
  dueCue,
  heardBefore,
  mustHold,
  transcriptEntries,
  type PlayCue,
} from "@/lib/playback";

export type Output = "voice" | "text";
type Mode = "standard" | "extended";
const DUCKED = 0.3;

/**
 * Plays the original lecture and voices each description at its scheduled time.
 * Standard: the lecture plays on, quieter, under the description. Extended: the video also
 * holds still where the schedule needs a pause. Output is either the recorded voice or text
 * announced to screen readers, never both, so nothing is described twice.
 */
export function DescribedPlayer({
  videoUrl,
  cues,
  speech,
  title,
}: {
  videoUrl: string;
  cues: Record<Mode, PlayCue[] | null>;
  speech: { start_s: number; text: string }[];
  title: string;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const audio = useRef<HTMLAudioElement>(null);
  const [enabled, setEnabled] = useState(true);
  const [mode, setMode] = useState<Mode>("standard");
  const [output, setOutput] = useState<Output>("voice");
  const [now, setNow] = useState(0);
  const [speaking, setSpeaking] = useState<PlayCue | null>(null);
  const [announce, setAnnounce] = useState("");

  const list = useMemo(() => cues[mode] ?? cues.standard ?? [], [cues, mode]);
  const heard = useRef<Set<string>>(new Set());
  const current = useRef<PlayCue | null>(null);
  const holding = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const userVolume = useRef(1);

  /** End the current description (finished, stopped or skipped). */
  const stop = useCallback((resume: boolean) => {
    const v = video.current;
    audio.current?.pause();
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    if (v && current.current) v.volume = userVolume.current;
    current.current = null;
    setSpeaking(null);
    if (holding.current) {
      holding.current = false;
      if (resume && v) void v.play().catch(() => {});
    }
  }, []);

  const start = useCallback(
    (cue: PlayCue) => {
      const v = video.current;
      if (!v) return;
      current.current = cue;
      heard.current.add(cue.id);
      setSpeaking(cue);
      userVolume.current = v.volume;
      if (output === "voice" && cue.audioUrl) {
        v.volume = Math.min(v.volume, DUCKED); // the <audio> below starts it (autoPlay)
      } else {
        setAnnounce(cue.text);
        timer.current = setTimeout(() => stop(true), cue.length * 1000);
      }
    },
    [output, stop],
  );

  // Check the playhead every frame while the video plays (timeupdate is too coarse).
  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const v = video.current;
      if (v) {
        const t = v.currentTime;
        setNow(t);
        if (enabled && !v.paused) {
          const cue = current.current;
          if (cue && mustHold(cue, t, mode === "extended") && !holding.current) {
            holding.current = true;
            v.pause();
          } else if (!cue) {
            const next = dueCue(list, t, heard.current);
            if (next) start(next);
          }
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [enabled, list, mode, start]);

  /** Changing a setting stops what is playing; what came before the playhead counts as heard. */
  const change = <T,>(set: (v: T) => void, nextList: () => PlayCue[]) => (v: T) => {
    stop(true);
    set(v);
    heard.current = heardBefore(nextList(), video.current?.currentTime ?? 0);
  };
  const listFor = (m: Mode) => cues[m] ?? cues.standard ?? [];

  useEffect(() => () => stop(false), [stop]);

  const onSeeked = () => {
    stop(false);
    heard.current = heardBefore(list, video.current?.currentTime ?? 0);
  };
  const onPause = () => {
    if (!holding.current) audio.current?.pause(); // the user paused: the description waits too
  };
  const onPlay = () => {
    if (holding.current) stop(false); // the user resumed during a hold: skip the rest
    else if (current.current && output === "voice") void audio.current?.play().catch(() => {});
  };

  const entries = useMemo(() => transcriptEntries(speech, list), [speech, list]);
  const active = activeEntry(entries, now);
  const extendedAvailable = Boolean(cues.extended?.length);

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <div className="space-y-3">
        <video
          ref={video}
          src={videoUrl}
          controls
          preload="metadata"
          aria-label={`${title}, with audio descriptions`}
          className="aspect-video w-full rounded-lg bg-black"
          onSeeked={onSeeked}
          onPause={onPause}
          onPlay={onPlay}
        />
        <p className="min-h-6 text-sm text-ink-2" aria-hidden={output === "text" ? true : undefined}>
          {speaking ? (
            <>
              <span className="font-medium text-ink">Describing: </span>
              {speaking.text}
            </>
          ) : (
            <span className="text-muted">{enabled ? `${list.length} description${list.length === 1 ? "" : "s"} in this mode.` : "Descriptions are off."}</span>
          )}
        </p>
        {speaking && output === "voice" && speaking.audioUrl && (
          <audio
            key={speaking.id}
            ref={audio}
            src={speaking.audioUrl}
            autoPlay
            onEnded={() => stop(true)}
            onError={() => stop(true)}
            aria-hidden="true"
          />
        )}
        {/* Text output: read by screen readers instead of the recorded voice. */}
        <p aria-live="polite" className="sr-only">
          {output === "text" && enabled ? announce : ""}
        </p>
        <fieldset className="flex flex-wrap items-center gap-x-6 gap-y-3 text-sm">
          <legend className="sr-only">Description settings</legend>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={enabled} onChange={(e) => change(setEnabled, () => list)(e.target.checked)} className="size-4 accent-accent" />
            Audio descriptions
          </label>
          <Choice
            label="Mode"
            value={mode}
            onChange={(m: Mode) => change(setMode, () => listFor(m))(m)}
            options={[
              { value: "standard", label: "Standard" },
              { value: "extended", label: "Extended (pauses the video)", disabled: !extendedAvailable },
            ]}
          />
          <Choice
            label="Output"
            value={output}
            onChange={change(setOutput, () => list)}
            options={[
              { value: "voice", label: "Voice", icon: AudioLines },
              { value: "text", label: "Screen reader text", icon: Captions },
            ]}
          />
        </fieldset>
      </div>
      <section aria-labelledby="player-transcript" className="min-w-0">
        <h3 id="player-transcript" className="text-sm font-medium text-ink">
          Transcript with descriptions
        </h3>
        <ol className="mt-2 max-h-[28rem] space-y-1 overflow-y-auto pr-1 text-sm">
          {entries.map((e, i) => (
            <li key={`${e.kind}-${e.start}-${i}`}>
              <button
                type="button"
                aria-current={i === active ? "true" : undefined}
                onClick={() => {
                  const v = video.current;
                  if (v) v.currentTime = e.start;
                }}
                className={cn(
                  "w-full rounded-md px-2 py-1 text-left hover:bg-sunken",
                  i === active && "bg-accent-soft",
                  e.kind === "description" && "border-l-2 border-accent",
                )}
              >
                <span className="mr-2 font-mono text-xs text-muted">{clock(e.start)}</span>
                {e.kind === "description" && <span className="font-medium text-ink">Description: </span>}
                <span className="text-ink-2">{e.text}</span>
              </button>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}

function Choice<T extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string; disabled?: boolean; icon?: typeof AudioLines }[];
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex items-center gap-3">
      <span aria-hidden="true" className="text-muted">
        {label}:
      </span>
      {options.map((o) => (
        <label key={o.value} className={cn("flex items-center gap-1.5", o.disabled && "opacity-50")}>
          <input
            type="radio"
            name={label}
            value={o.value}
            checked={value === o.value}
            disabled={o.disabled}
            onChange={() => onChange(o.value)}
            className="size-4 accent-accent"
          />
          {o.icon && <o.icon aria-hidden="true" className="size-4" />}
          {o.label}
        </label>
      ))}
    </div>
  );
}

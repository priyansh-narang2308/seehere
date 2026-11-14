/**
 * Described playback rules, kept free of the DOM so they can be tested.
 *
 * A description starts when the video reaches its start time. In standard mode the lecture keeps
 * playing (quieter) underneath. In extended mode the video also holds still at `pauseAt` until
 * the description has finished. Each description plays at most once per pass; seeking resets
 * which ones count as already heard.
 */

export type PlayCue = {
  id: string;
  text: string;
  start: number;
  /** Measured length of the spoken description, in seconds. */
  length: number;
  /** Extended mode: how long the video holds still. */
  pause: number;
  audioUrl: string | null;
};

/** How late (s) a description may still start after its time, e.g. after a coarse tick. */
export const START_WINDOW = 0.6;

export const pauseAt = (c: PlayCue) => c.start + c.length - c.pause;

/** The next description that should start at time `t`, if any. */
export function dueCue(cues: PlayCue[], t: number, heard: ReadonlySet<string>): PlayCue | null {
  return cues.find((c) => !heard.has(c.id) && c.start <= t && t < c.start + START_WINDOW) ?? null;
}

/** After a seek to `t`: descriptions that started before `t` count as heard. */
export function heardBefore(cues: PlayCue[], t: number): Set<string> {
  return new Set(cues.filter((c) => c.start < t - 0.05).map((c) => c.id));
}

/** Extended mode: the video must hold now (the description is still speaking). */
export const mustHold = (c: PlayCue, t: number, extended: boolean) => extended && c.pause > 0 && t >= pauseAt(c);

export type TranscriptEntry = { kind: "speech" | "description"; start: number; text: string };

export function transcriptEntries(speech: { start_s: number; text: string }[], cues: PlayCue[]): TranscriptEntry[] {
  return [
    ...speech.map((s) => ({ kind: "speech" as const, start: s.start_s, text: s.text })),
    ...cues.map((c) => ({ kind: "description" as const, start: c.start, text: c.text })),
  ].sort((a, b) => a.start - b.start || (a.kind === "speech" ? -1 : 1));
}

/** Index of the entry being heard at `t` (the last one that has started), or -1. */
export function activeEntry(entries: TranscriptEntry[], t: number): number {
  let found = -1;
  entries.forEach((e, i) => {
    if (e.start <= t + 0.05) found = i;
  });
  return found;
}

/** m:ss */
export const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

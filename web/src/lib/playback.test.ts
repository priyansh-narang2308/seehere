import { describe, expect, it } from "vitest";
import { activeEntry, clock, dueCue, heardBefore, mustHold, pauseAt, transcriptEntries, type PlayCue } from "./playback";

const a: PlayCue = { id: "a", text: "Next steps.", start: 2, length: 1.5, pause: 0, audioUrl: "/a.wav" };
const b: PlayCue = { id: "b", text: "Revenue chart.", start: 5, length: 2, pause: 1.2, audioUrl: "/b.wav" };

describe("described playback", () => {
  it("starts each description once, near its time", () => {
    expect(dueCue([a, b], 1.9, new Set())).toBeNull();
    expect(dueCue([a, b], 2.2, new Set())).toBe(a);
    expect(dueCue([a, b], 2.2, new Set(["a"]))).toBeNull(); // never twice in one pass
    expect(dueCue([a, b], 3, new Set())).toBeNull(); // too late: skipped rather than out of sync
  });

  it("holds the video only in extended mode, after the usable silence", () => {
    expect(pauseAt(b)).toBeCloseTo(5.8);
    expect(mustHold(b, 5.7, true)).toBe(false);
    expect(mustHold(b, 5.8, true)).toBe(true);
    expect(mustHold(b, 6, false)).toBe(false);
    expect(mustHold(a, 3, true)).toBe(false);
  });

  it("treats descriptions before a seek target as heard", () => {
    expect([...heardBefore([a, b], 4)]).toEqual(["a"]);
    expect([...heardBefore([a, b], 2)]).toEqual([]); // seeking to a description's start replays it
  });

  it("merges speech and descriptions in time order and follows the playhead", () => {
    const entries = transcriptEntries([{ start_s: 0, text: "Hello." }, { start_s: 5, text: "Look here." }], [a, b]);
    expect(entries.map((e) => `${e.kind}:${e.start}`)).toEqual(["speech:0", "description:2", "speech:5", "description:5"]);
    expect(activeEntry(entries, 0)).toBe(0);
    expect(activeEntry(entries, 3)).toBe(1);
    expect(activeEntry(entries, 6)).toBe(3);
    expect(clock(65.9)).toBe("1:05");
  });
});

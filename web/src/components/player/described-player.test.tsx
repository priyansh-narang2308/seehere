import { act, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { PlayCue } from "@/lib/playback";
import { DescribedPlayer } from "./described-player";

const a: PlayCue = { id: "a", text: "On screen: “Next steps”.", start: 2, length: 1.5, pause: 0, audioUrl: "/api/audio/a" };
const b: PlayCue = { id: "b", text: "On screen: “Revenue”.", start: 5, length: 2, pause: 1.2, audioUrl: "/api/audio/b" };
const speech = [{ start_s: 0, text: "Hello and welcome." }];

let frame: FrameRequestCallback | null = null;
const tickAt = (video: HTMLVideoElement, t: number, paused = false) => {
  video.currentTime = t;
  Object.defineProperty(video, "paused", { configurable: true, value: paused });
  act(() => frame?.(0));
};

beforeEach(() => {
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
    frame = cb;
    return 1;
  });
  vi.stubGlobal("cancelAnimationFrame", () => {});
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

const setup = (extended: PlayCue[] | null = [a, b]) => {
  const view = render(<DescribedPlayer videoUrl="/v.mp4" cues={{ standard: [a], extended }} speech={speech} title="Week 1" />);
  return { ...view, video: screen.getByLabelText("Week 1, with audio descriptions") as HTMLVideoElement };
};

describe("DescribedPlayer", () => {
  it("voices a description at its time, lowering the lecture, once per pass", async () => {
    const { video, container } = setup();
    video.volume = 1;
    tickAt(video, 1.9);
    expect(container.querySelector("audio")).toBeNull();
    tickAt(video, 2.05);
    const clip = container.querySelector("audio")!;
    expect(clip).toHaveAttribute("src", "/api/audio/a");
    expect(video.volume).toBeCloseTo(0.3);
    expect(screen.getByText("On screen: “Next steps”.", { selector: "p *, p" })).toBeInTheDocument();
    fireEvent.ended(clip);
    expect(container.querySelector("audio")).toBeNull();
    expect(video.volume).toBe(1);
    tickAt(video, 2.2); // already heard in this pass
    expect(container.querySelector("audio")).toBeNull();
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });

  it("still fires from timeupdate in a background tab, where animation frames stop", () => {
    const { video, container } = setup();
    video.currentTime = 2.1;
    Object.defineProperty(video, "paused", { configurable: true, value: false });
    fireEvent.timeUpdate(video);
    expect(container.querySelector("audio")).toHaveAttribute("src", "/api/audio/a");
  });

  it("extended mode holds the video until the description finishes", async () => {
    const { video, container } = setup();
    await userEvent.click(screen.getByRole("radio", { name: "Extended (pauses the video)" }));
    tickAt(video, 5.0);
    expect(container.querySelector("audio")).toHaveAttribute("src", "/api/audio/b");
    tickAt(video, 5.7);
    expect(HTMLMediaElement.prototype.pause).not.toHaveBeenCalled();
    tickAt(video, 5.85);
    expect(HTMLMediaElement.prototype.pause).toHaveBeenCalledTimes(1); // hold the frame
    fireEvent.ended(container.querySelector("audio")!);
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalled(); // and resume afterwards
  });

  it("screen reader text replaces the voice, never both", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const { video, container } = setup(null);
    expect(screen.getByRole("radio", { name: "Extended (pauses the video)" })).toBeDisabled();
    fireEvent.click(screen.getByRole("radio", { name: "Screen reader text" }));
    tickAt(video, 2.05);
    expect(container.querySelector("audio")).toBeNull();
    const live = container.querySelector('[aria-live="polite"]')!;
    expect(live).toHaveTextContent("On screen: “Next steps”.");
    act(() => vi.advanceTimersByTime(1500)); // the description's length
    expect(screen.getByText("1 description in this mode.")).toBeInTheDocument();
  });

  it("switching descriptions off stops them; the transcript seeks and follows the playhead", async () => {
    const { video, container } = setup();
    tickAt(video, 2.05);
    expect(container.querySelector("audio")).not.toBeNull();
    await userEvent.click(screen.getByRole("checkbox", { name: "Audio descriptions" }));
    expect(container.querySelector("audio")).toBeNull();
    expect(screen.getByText("Descriptions are off.")).toBeInTheDocument();
    const items = within(screen.getByRole("list")).getAllByRole("button");
    expect(items.map((i) => i.textContent)).toEqual(["0:00Hello and welcome.", "0:02Description: On screen: “Next steps”."]);
    expect(items[1]).toHaveAttribute("aria-current", "true");
    await userEvent.click(items[0]);
    expect(video.currentTime).toBe(0);
  });
});

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Project } from "@/lib/api";
import { ProjectList } from "./project-list";
import { SourceFacts } from "./source-facts";

const project: Project = {
  id: "0b8f7c1e-1d2a-4c3b-9e8f-7a6b5c4d3e2f",
  title: "Intro to Data Analysis, Lecture 7",
  status: "uploaded",
  created_at: "2026-11-14T10:00:00Z",
  expires_at: "2026-11-15T10:00:00Z",
  source: {
    original_filename: "lecture7.mp4",
    mime_type: "video/mp4",
    size_bytes: 52_428_800,
    duration_s: 3725,
    width: 1920,
    height: 1080,
    video_codec: "h264",
    audio_codec: "aac",
  },
};

afterEach(() => vi.unstubAllGlobals());

describe("ProjectList", () => {
  it("shows a loading status while the request is pending", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    render(<ProjectList />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading projects…");
  });

  it("lists projects with their measured facts and a link to each", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json([project])));
    const { container } = render(<ProjectList />);
    const link = await screen.findByRole("link", { name: project.title });
    expect(link).toHaveAttribute("href", `/projects/${project.id}/processing`);
    const item = within(screen.getByRole("listitem"));
    expect(item.getByText(/1:02:05/)).toBeInTheDocument();
    expect(item.getByText(/50 MB/)).toBeInTheDocument();
    expect(item.getByText("MP4")).toBeInTheDocument();
    expect(item.getByText("Uploaded")).toBeInTheDocument();
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });

  it("offers an upload link when there are no projects", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json([])));
    render(<ProjectList />);
    expect(await screen.findByText("No projects yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Upload a lecture" })).toHaveAttribute("href", "/upload");
  });

  it("explains a failure and retries on request", async () => {
    const fetch = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("down"))
      .mockResolvedValueOnce(Response.json([project]));
    vi.stubGlobal("fetch", fetch);
    render(<ProjectList />);
    expect(await screen.findByText("Projects could not be loaded")).toBeInTheDocument();
    expect(screen.getByText("The SeeHere API could not be reached.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("link", { name: project.title })).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});

describe("SourceFacts", () => {
  it("shows what the server measured about the upload", () => {
    render(<SourceFacts project={project} />);
    expect(screen.getByRole("heading", { name: "Upload checked" })).toBeInTheDocument();
    for (const [term, value] of [
      ["File", "lecture7.mp4"],
      ["Length", "1:02:05"],
      ["Resolution", "1920 × 1080"],
      ["Size", "50 MB"],
      ["Format", "video/mp4"],
      ["Codecs", "h264 + aac"],
    ]) {
      expect(screen.getByText(term).nextElementSibling).toHaveTextContent(value);
    }
    expect(screen.getByText(/Marked to expire/)).toHaveTextContent("15 Nov 2026, 10:00 UTC");
  });

  it("says so when no source video is attached", () => {
    render(<SourceFacts project={{ ...project, source: null, expires_at: null }} />);
    expect(screen.getByText("No source video is attached to this project.")).toBeInTheDocument();
    expect(screen.queryByText(/Marked to expire/)).toBeNull();
  });
});

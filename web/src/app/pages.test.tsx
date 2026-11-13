import { render, screen } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, describe, expect, it, vi } from "vitest";
import NotFound from "./not-found";
import Home from "./page";
import MethodologyPage from "./methodology/page";
import ProjectsPage from "./projects/page";
import ProcessingPage from "./projects/[projectId]/processing/page";
import ResultsPage from "./projects/[projectId]/results/page";
import StatusPage from "./status/page";
import UploadPage from "./upload/page";
import { pipelineStages } from "@/lib/pipeline";

const pages: [string, () => React.ReactElement][] = [
  ["Home", Home],
  ["Upload", UploadPage],
  ["Projects", ProjectsPage],
  ["Methodology", MethodologyPage],
  ["Processing", ProcessingPage],
  ["Results", ResultsPage],
  ["Status", StatusPage],
  ["Not found", NotFound],
];

afterEach(() => vi.unstubAllGlobals());

describe.each(pages)("%s page", (_name, Page) => {
  it("has exactly one h1 and no axe violations", async () => {
    // The status page fetches the API; keep it pending so no network is used.
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    // Pages render inside the root layout's <main>, so mirror that here.
    const { container } = render(
      <main>
        <Page />
      </main>,
    );
    expect(container.querySelectorAll("h1")).toHaveLength(1);
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
  });
});

describe("honesty of in-progress pages", () => {
  it("states that uploads are not open, with no file input on the page", () => {
    const { container } = render(<UploadPage />);
    expect(screen.getByRole("heading", { name: /uploads are not open/i })).toBeInTheDocument();
    expect(container.querySelector('input[type="file"]')).toBeNull();
  });

  it("reports the real number of built pipeline stages", () => {
    render(<MethodologyPage />);
    const built = pipelineStages.filter((s) => s.status === "built").length;
    expect(screen.getByText(new RegExp(`${built} of ${pipelineStages.length} stages are built`))).toBeInTheDocument();
    expect(screen.getAllByText("Not built yet")).toHaveLength(pipelineStages.length - built);
  });

  it("never claims WCAG certification", () => {
    render(<MethodologyPage />);
    expect(screen.getByText(/does not certify/i)).toBeInTheDocument();
  });
});

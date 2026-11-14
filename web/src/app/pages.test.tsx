import { render, screen } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, describe, expect, it, vi } from "vitest";
import NotFound from "./not-found";
import Home from "./page";
import MethodologyPage from "./methodology/page";
import ProjectsPage from "./projects/page";
import StatusPage from "./status/page";
import UploadPage from "./upload/page";
import { ToastProvider } from "@/components/ui/toast";
import { pipelineStages } from "@/lib/pipeline";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }), usePathname: () => "/" }));

// The Processing and Results pages load their project on the server (server-only module); its content is
// covered by component tests and the browser check, so they are not rendered here.

const pages: [string, () => React.ReactElement][] = [
  ["Home", Home],
  ["Upload", UploadPage],
  ["Projects", ProjectsPage],
  ["Methodology", MethodologyPage],
  ["Status", StatusPage],
  ["Not found", NotFound],
];

afterEach(() => vi.unstubAllGlobals());

describe.each(pages)("%s page", (_name, Page) => {
  it("has exactly one h1 and no axe violations", async () => {
    // Pages that fetch the API stay pending so no network is used.
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    // Pages render inside the root layout's <main>, so mirror that here.
    const { container } = render(
      <ToastProvider>
        <main>
          <Page />
        </main>
      </ToastProvider>,
    );
    expect(container.querySelectorAll("h1")).toHaveLength(1);
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
  });
});

describe("honesty of in-progress pages", () => {
  it("asks for a rights confirmation and is truthful about retention", async () => {
    const config = { max_upload_bytes: 1, max_video_duration_s: 1, accept: ".mp4", formats: ["MP4"], retention_hours: 24 };
    vi.stubGlobal("fetch", vi.fn(async () => Response.json(config)));
    const { container } = render(
      <ToastProvider>
        <UploadPage />
      </ToastProvider>,
    );
    expect(container.querySelector('input[type="file"]')).not.toBeNull();
    expect(screen.getByRole("checkbox", { name: /own this video or have permission/i })).toBeInTheDocument();
    expect(await screen.findByText(/deleted 24 hours after upload/)).toBeInTheDocument();
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

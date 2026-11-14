import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Cue, CueLedger } from "@/lib/api";
import { CuesView } from "./cues-view";

const cue: Cue = {
  id: "c1",
  visual_unit_id: "u1",
  text_short: "On screen: “Revenue fell in 2023”.",
  text_medium: null,
  text_long: null,
  anchor_t_s: 4,
  priority: 0.7,
  verification_state: "needs_review",
  review_status: "pending",
};

const ledger = (over: Partial<Cue>, decisions: CueLedger["decisions"] = []): CueLedger => ({
  cue: { ...cue, ...over },
  evidence: [
    {
      kind: "visual_unit",
      note: "ocr unit",
      frame: null,
      ocr_region: null,
      slide: null,
      transcript: null,
      visual_unit: { kind: "text_block", label: "Revenue", box: null, t_start_s: 0, t_end_s: 8, coverage: 0, said: [], unsaid: ["Revenue fell in 2023"] },
    },
  ],
  checks: [],
  decisions,
});

type Call = { url: string; init?: RequestInit };

function stub(reply: (call: Call) => unknown) {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      return Response.json(reply({ url, init }));
    }),
  );
  return calls;
}

afterEach(() => vi.unstubAllGlobals());

describe("CuesView review", () => {
  it("shows that a cue is held and approves it with the app header", async () => {
    const at = "2026-11-14T10:00:00Z";
    const calls = stub(() => ledger({ review_status: "approved" }, [{ action: "approve", previous_text: cue.text_short, new_text: cue.text_short, note: null, created_at: at }]));
    const onChanged = vi.fn();
    const { container } = render(<CuesView cues={[cue]} onChanged={onChanged} />);
    expect(screen.getByText(/held until approved/)).toBeInTheDocument();

    const review = within(screen.getByRole("group", { name: "Review" }));
    await userEvent.click(review.getByRole("button", { name: "Approve" }));
    expect(calls[0].url).toBe("/api/cues/c1/review");
    expect(calls[0].init?.method).toBe("POST");
    expect(new Headers(calls[0].init?.headers).get("X-SeeHere-Request")).toBe("1");
    expect(JSON.parse(String(calls[0].init?.body))).toEqual({ action: "approve" });
    expect(await screen.findByText("Approved", { selector: "span" })).toBeInTheDocument();
    expect(screen.queryByText(/held until approved/)).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Approved. The schedule is being updated.");
    expect(onChanged).toHaveBeenCalledOnce();

    await userEvent.click(screen.getByRole("button", { name: "Show evidence" }));
    expect(within(screen.getByRole("list", { name: "Review history" })).getByRole("listitem")).toHaveTextContent("Approved");
    expect(within(screen.getByRole("list", { name: "Not said aloud" })).getByRole("listitem")).toHaveTextContent("Revenue fell in 2023");
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });

  it("edits a description, and reports a rejected review", async () => {
    const edited = "On screen: “Revenue fell”.";
    const calls = stub(({ init }) => {
      const body = JSON.parse(String(init?.body));
      return ledger({ text_short: body.text, review_status: "approved", verification_state: "uncertain" });
    });
    render(<CuesView cues={[cue]} />);
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    const box = screen.getByLabelText("Corrected description");
    expect(box).toHaveValue(cue.text_short);
    await userEvent.clear(box);
    await userEvent.type(box, edited);
    await userEvent.click(screen.getByRole("button", { name: "Save and approve" }));
    expect(JSON.parse(String(calls[0].init?.body))).toEqual({ action: "edit", text: edited });
    expect(await screen.findByText(edited)).toBeInTheDocument();
    expect(screen.getByText("Uncertain")).toBeInTheDocument();

    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json({ error: { code: "invalid_review", message: "The text is empty." } }, { status: 422 })),
    );
    await userEvent.click(screen.getByRole("button", { name: "Reject" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The text is empty.");
  });
});

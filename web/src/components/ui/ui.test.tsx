import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import axe from "axe-core";
import { InteractiveShowcase } from "@/app/design/showcase";
import { Button } from "./button";
import { Dialog, DialogContent, DialogTrigger } from "./dialog";
import { Field, Input } from "./field";
import { Progress } from "./misc";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./tabs";
import { ToastProvider } from "./toast";
import { VerificationBadge } from "./verification-badge";

describe("Button", () => {
  it("defaults to type=button so it never submits forms by accident", () => {
    render(<Button>Go</Button>);
    expect(screen.getByRole("button", { name: "Go" })).toHaveAttribute("type", "button");
  });

  it("loading state is busy, disabled and keeps its accessible name", async () => {
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        Processing
      </Button>,
    );
    const btn = screen.getByRole("button", { name: "Processing" });
    expect(btn).toHaveAttribute("aria-busy", "true");
    expect(btn).toBeDisabled();
    await userEvent.click(btn);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("asChild renders the child element with button styles", () => {
    render(
      <Button asChild>
        <a href="/upload">Upload</a>
      </Button>,
    );
    const link = screen.getByRole("link", { name: "Upload" });
    expect(link.className).toContain("rounded-md");
  });
});

describe("Field", () => {
  it("associates label, hint and error with the control", () => {
    render(
      <Field label="Lecture title" hint="Shown to students." error="Enter a lecture title." required>
        <Input />
      </Field>,
    );
    const input = screen.getByRole("textbox", { name: /lecture title/i });
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toBeRequired();
    expect(input).toHaveAccessibleDescription("Shown to students. Enter a lecture title.");
  });
});

describe("Dialog", () => {
  it("moves focus inside, closes on Escape and returns focus to the trigger", async () => {
    const user = userEvent.setup();
    render(
      <Dialog>
        <DialogTrigger asChild>
          <Button>Open</Button>
        </DialogTrigger>
        <DialogContent title="Reject cue?" description="This removes it from the schedule.">
          <Button>Confirm</Button>
        </DialogContent>
      </Dialog>,
    );
    const trigger = screen.getByRole("button", { name: "Open" });
    await user.click(trigger);
    const dialog = screen.getByRole("dialog", { name: "Reject cue?" });
    expect(dialog).toHaveAccessibleDescription("This removes it from the schedule.");
    expect(dialog.contains(document.activeElement)).toBe(true);
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});

describe("Tabs", () => {
  it("switches panels with arrow keys", async () => {
    const user = userEvent.setup();
    render(
      <Tabs defaultValue="a">
        <TabsList aria-label="Mode">
          <TabsTrigger value="a">Standard</TabsTrigger>
          <TabsTrigger value="b">Extended</TabsTrigger>
        </TabsList>
        <TabsContent value="a">Standard panel</TabsContent>
        <TabsContent value="b">Extended panel</TabsContent>
      </Tabs>,
    );
    await user.click(screen.getByRole("tab", { name: "Standard" }));
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Extended" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Extended panel");
  });
});

describe("Progress and verification badge", () => {
  it("progress exposes name and value", () => {
    render(<Progress label="Transcribing speech" value={64} />);
    const bar = screen.getByRole("progressbar", { name: "Transcribing speech" });
    expect(bar).toHaveAttribute("aria-valuenow", "64");
    expect(bar).toHaveAttribute("aria-valuetext", "64%");
  });

  it("verification state is conveyed by text, not colour alone", () => {
    render(<VerificationBadge state="needs_review" />);
    expect(screen.getByText("Needs human review")).toBeInTheDocument();
  });
});

describe("Design showcase", () => {
  it("has no axe violations (jsdom; colour contrast is tested via tokens)", async () => {
    const { container } = render(
      <ToastProvider>
        <main>
          <InteractiveShowcase />
        </main>
      </ToastProvider>,
    );
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
  });
});

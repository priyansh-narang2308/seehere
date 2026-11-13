import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { isUuid, shortId } from "@/lib/ids";
import { isActivePath } from "@/lib/navigation";
import { MainNavView } from "./main-nav";

describe("isActivePath", () => {
  it.each([
    ["/projects", "/projects", true],
    ["/projects/0b7c/results", "/projects", true],
    ["/projectsx", "/projects", false],
    ["/", "/projects", false],
    ["/", "/", true],
    ["/upload", "/", false],
    [null, "/projects", false],
  ])("%s vs %s → %s", (pathname, href, expected) => {
    expect(isActivePath(pathname, href)).toBe(expected);
  });
});

describe("isUuid", () => {
  it("accepts a v4 UUID and rejects everything else", () => {
    expect(isUuid("3f2a9c1e-7b4d-4e8a-9c0f-1a2b3c4d5e6f")).toBe(true);
    expect(isUuid("3F2A9C1E-7B4D-4E8A-9C0F-1A2B3C4D5E6F")).toBe(true);
    expect(isUuid("not-a-uuid")).toBe(false);
    expect(isUuid("../../etc/passwd")).toBe(false);
    expect(isUuid("3f2a9c1e-7b4d-4e8a-9c0f-1a2b3c4d5e6f-extra")).toBe(false);
    expect(shortId("3f2a9c1e-7b4d-4e8a-9c0f-1a2b3c4d5e6f")).toBe("3f2a9c1e");
  });
});

describe("MainNavView", () => {
  it("marks the section of the current page with aria-current", () => {
    render(<MainNavView pathname="/projects/3f2a9c1e/results" />);
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(nav).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Projects" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Methodology" })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("link", { name: /upload lecture/i })).not.toHaveAttribute("aria-current");
  });

  it("marks nothing as current while the path is unknown", () => {
    render(<MainNavView pathname={null} />);
    for (const link of screen.getAllByRole("link")) expect(link).not.toHaveAttribute("aria-current");
  });

  it("opens the mobile menu, closes it with Escape and returns focus to the toggle", async () => {
    const user = userEvent.setup();
    render(<MainNavView pathname="/" />);
    const toggle = screen.getByRole("button", { name: "Open menu" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    // The closed menu is hidden from assistive technology.
    expect(screen.getAllByRole("navigation", { name: "Main" })).toHaveLength(1);

    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(toggle).toHaveAccessibleName("Close menu");
    const menu = document.getElementById(toggle.getAttribute("aria-controls")!);
    expect(menu).toBeVisible();
    expect(screen.getAllByRole("navigation", { name: "Main" })).toHaveLength(2);

    await user.keyboard("{Escape}");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(menu).not.toBeVisible();
    expect(toggle).toHaveFocus();
  });

  it("closes the mobile menu when the route changes", async () => {
    const user = userEvent.setup();
    const { rerender } = render(<MainNavView pathname="/" />);
    await user.click(screen.getByRole("button", { name: "Open menu" }));
    rerender(<MainNavView pathname="/methodology" />);
    expect(screen.getByRole("button", { name: "Open menu" })).toHaveAttribute("aria-expanded", "false");
  });
});

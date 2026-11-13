import { describe, expect, it } from "vitest";
import { color, contrastRatio } from "./tokens";

describe("contrastRatio", () => {
  it("matches known WCAG reference values", () => {
    expect(contrastRatio("#000000", "#ffffff")).toBeCloseTo(21, 5);
    expect(contrastRatio("#ffffff", "#ffffff")).toBeCloseTo(1, 5);
    expect(contrastRatio("#777777", "#ffffff")).toBeCloseTo(4.48, 2);
  });
});

// Every text/background pair the components actually use. WCAG 2.x AA requires 4.5:1 for body text.
const textPairs: [string, keyof typeof color, keyof typeof color][] = [
  ["ink on canvas", "ink", "canvas"],
  ["ink-2 on canvas", "ink2", "canvas"],
  ["muted on canvas", "muted", "canvas"],
  ["muted on surface", "muted", "surface"],
  ["muted on surface-muted", "muted", "surfaceMuted"],
  ["muted on sunken", "muted", "sunken"],
  ["ink-2 on sunken", "ink2", "sunken"],
  ["accent on surface", "accent", "surface"],
  ["accent on canvas (wordmark)", "accent", "canvas"],
  ["accent-strong on surface (links)", "accentStrong", "surface"],
  ["accent-strong on canvas (links)", "accentStrong", "canvas"],
  ["accent-strong on accent-soft", "accentStrong", "accentSoft"],
  ["success on success-soft", "success", "successSoft"],
  ["warning on warning-soft", "warning", "warningSoft"],
  ["danger on danger-soft", "danger", "dangerSoft"],
  ["danger on surface", "danger", "surface"],
];

describe("design tokens meet WCAG AA text contrast", () => {
  it.each(textPairs)("%s", (_name, fg, bg) => {
    expect(contrastRatio(color[fg], color[bg])).toBeGreaterThanOrEqual(4.5);
  });

  it.each([
    ["white on accent (primary button)", "accent"],
    ["white on accent-hover", "accentHover"],
    ["white on danger (danger button)", "danger"],
    ["white on ink (skip link)", "ink"],
  ] as const)("%s", (_name, bg) => {
    expect(contrastRatio("#ffffff", color[bg])).toBeGreaterThanOrEqual(4.5);
  });
});

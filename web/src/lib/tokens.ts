/**
 * Colour tokens mirrored from globals.css so they can be contrast-tested and used in
 * canvas/SVG contexts. Keep both files in sync.
 */
export const color = {
  canvas: "#f7f5f0",
  surface: "#ffffff",
  surfaceMuted: "#fbfaf7",
  sunken: "#f1eee8",
  border: "#e6e3dc",
  borderStrong: "#d3cfc6",
  ink: "#0e1a33",
  ink2: "#3b4660",
  muted: "#5b6475",
  faint: "#8a91a0",
  accent: "#2f5bff",
  accentHover: "#2449d8",
  accentStrong: "#1f3fbf",
  accentSoft: "#eaf0ff",
  accentLine: "#bfd0ff",
  success: "#17734c",
  successSoft: "#e7f5ee",
  warning: "#8a5a0b",
  warningSoft: "#fff5e3",
  danger: "#b42318",
  dangerSoft: "#feeceb",
} as const;

export type ColorToken = keyof typeof color;

function channel(c: number): number {
  const s = c / 255;
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
}

/** WCAG 2.x relative luminance of a #rrggbb colour. */
export function luminance(hex: string): number {
  const m = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!m) throw new Error(`invalid hex colour: ${hex}`);
  const n = parseInt(m[1], 16);
  return 0.2126 * channel((n >> 16) & 255) + 0.7152 * channel((n >> 8) & 255) + 0.0722 * channel(n & 255);
}

/** WCAG 2.x contrast ratio between two #rrggbb colours (1–21). */
export function contrastRatio(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

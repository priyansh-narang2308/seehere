import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// Teach tailwind-merge about our custom theme keys so `shadow-card` is treated as a shadow size
// (not a shadow colour) and custom radii merge correctly.
const twMerge = extendTailwindMerge({
  extend: {
    theme: {
      shadow: ["xs", "card", "pop"],
      radius: ["sm", "md", "lg", "xl"],
    },
  },
});

/** Merge class names, letting later Tailwind utilities override earlier ones. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

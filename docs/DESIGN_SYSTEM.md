# Design System

The live reference is at **`/design`** (`web/src/app/design/`). Tokens are defined once, in `web/src/app/globals.css` (`@theme`), and mirrored for tests in `web/src/lib/tokens.ts`. If you change one, change the other: `tokens.test.ts` asserts that the pairs we use pass contrast.

## Principles
1. **Calm, editorial, trustworthy.** Warm paper canvas, deep-navy ink, one blue accent. No gradients, no decorative motion.
2. **State is never colour-only.** Every verification state pairs colour with an icon and a text label.
3. **Keyboard first.** Every interactive primitive is reachable and operable by keyboard, with a visible 2px accent focus ring (`:focus-visible`).
4. **Respect the user's settings.** `prefers-reduced-motion` disables animation and transitions globally.
5. **Honest UI.** Sample content is labelled as a sample. No fake metrics.

## Tokens

### Colour (light theme only, for now)
| Token | Hex | Use |
|---|---|---|
| `canvas` | #f7f5f0 | Page background |
| `surface` / `surface-muted` / `sunken` | #ffffff / #fbfaf7 / #f1eee8 | Cards, subtle fills, wells |
| `border` / `border-strong` | #e6e3dc / #d3cfc6 | Dividers, input borders |
| `ink` | #0e1a33 | Primary text |
| `ink-2` | #3b4660 | Secondary text |
| `muted` | #5b6475 | Hints, metadata (passes AA on canvas and surface) |
| `faint` | #8a91a0 | **Decorative only.** Never used for text. |
| `accent` / `accent-hover` / `accent-strong` | #2f5bff / #2449d8 / #1f3fbf | Primary actions; accent text on tints |
| `accent-soft` / `accent-line` | #eaf0ff / #bfd0ff | Tints and outlines |
| `success` (+ `-soft`, `-line`) | #17734c | Verified text match |
| `warning` (+ `-soft`, `-line`) | #8a5a0b | Uncertain |
| `danger` (+ `-soft`, `-line`) | #b42318 | Needs review, errors |

Contrast is computed with the WCAG 2.x relative-luminance formula (`contrastRatio()` in `tokens.ts`). Every text/background pair used in the UI is tested at **≥ 4.5:1**, and the `/design` page displays the live ratios.

### Type
- **Inter** (UI and body) and **JetBrains Mono** (timecodes, IDs, eyebrows), both self-hosted via `next/font`.
- The scale is shown on `/design`: Display 48 / H1 30 / H2 20 / Body 16 / Small 14 / Mono 14.

### Radius, shadow, motion
- Radius: `sm` 6 · `md` 10 · `lg` 14 · `xl` 20.
- Shadow: `xs` (controls) · `card` (cards) · `pop` (dialogs, toasts).
- Motion: `fade-in` and `pop-in` only, ≤ 200 ms, both disabled under reduced motion.

## Components (`web/src/components/ui/`)
| Component | Notes |
|---|---|
| `Button` | Variants: primary / secondary / ghost / danger / link. Sizes: sm / md / lg / icon. `type="button"` by default. `loading` sets `aria-busy`, disables the button and shows a spinner. `asChild` renders as a link. |
| `Badge` | Tones: neutral / accent / success / warning / danger. Shapes: pill / tag. |
| `VerificationBadge` | One component for the four states (below): icon + label + tone, plus help text exported for legends. |
| `Card` (+ Header, Title, Description, Content, Footer), `Eyebrow` | `CardTitle` and `Eyebrow` take `as` so heading levels stay correct. |
| `Field`, `Input`, `Textarea`, `Checkbox` | `Field` wires `label[for]`, `aria-describedby` (hint and error), `aria-invalid` and `required` automatically. |
| `Dialog` | Radix. Requires `title` and `description`. Traps focus, closes on Esc, and returns focus to the trigger. |
| `Tabs` | Radix. Arrow-key navigation, roving tabindex. |
| `Toast` / `useToast()` | Radix. Errors are announced assertively (`foreground`); everything else politely. |
| `Progress` | `role="progressbar"` with `aria-valuenow` and a human `aria-valuetext`. |
| `SkipLink`, `VisuallyHidden`, `Kbd`, `Spinner` | Utilities. The skip link targets `#main`, so every page must have `<main id="main">`. |

## Verification states
These are the product's core vocabulary. Never invent another state in the UI.

| State (API value) | Label | Meaning |
|---|---|---|
| `verified_text_match` | Verified text match | Text in the description matches OCR text extracted from the source frame. This is **not** a claim that the whole description is factually correct. |
| `corroborated` | Corroborated | Supported by the transcript or by slides, but with no exact text match. |
| `uncertain` | Uncertain | Weak or conflicting evidence. Shown to the reviewer with a warning. |
| `needs_review` | Needs human review | Must be checked by a person before it is published. |

## Accessibility verification (Task 02)
- `axe-core` in Vitest/jsdom on the full showcase: 0 violations (colour contrast is covered by token tests instead, because jsdom cannot compute it).
- `axe-core` in a real browser on `/design`: 0 violations and 44 passing rules, including colour contrast. Also 0 with the dialog open.
- Manual keyboard checks in a real browser: the skip link appears on first Tab; the dialog opens with Enter, Esc closes it, and focus returns to the trigger.
- 375px width: no horizontal overflow.

This is evidence of good practice, **not** a WCAG conformance claim or certification.

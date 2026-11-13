import type { Metadata } from "next";
import Link from "next/link";
import { Logo, LogoMark } from "@/components/brand/logo";
import { Eyebrow } from "@/components/ui/card";
import { color, contrastRatio } from "@/lib/tokens";
import { InteractiveShowcase } from "./showcase";

export const metadata: Metadata = {
  title: "Design system",
  description: "SeeHere tokens and accessible UI primitives.",
};

const swatches: {
  name: string;
  token: keyof typeof color;
  on: keyof typeof color;
  usage: string;
}[] = [
  { name: "Ink", token: "ink", on: "canvas", usage: "Primary text" },
  { name: "Ink 2", token: "ink2", on: "canvas", usage: "Secondary text" },
  { name: "Muted", token: "muted", on: "canvas", usage: "Hints, metadata" },
  {
    name: "Accent",
    token: "accent",
    on: "surface",
    usage: "Primary actions, references",
  },
  {
    name: "Accent strong",
    token: "accentStrong",
    on: "accentSoft",
    usage: "Accent text on tint",
  },
  { name: "Success", token: "success", on: "successSoft", usage: "Verified" },
  { name: "Warning", token: "warning", on: "warningSoft", usage: "Uncertain" },
  {
    name: "Danger",
    token: "danger",
    on: "dangerSoft",
    usage: "Needs review, errors",
  },
];

const typeScale = [
  {
    label: "Display",
    className: "text-5xl font-extrabold tracking-[-0.035em]",
    sample: "SeeHere",
  },
  {
    label: "H1",
    className: "text-3xl font-bold tracking-tight",
    sample: "Lecture 7 review",
  },
  {
    label: "H2",
    className: "text-xl font-semibold tracking-tight",
    sample: "Visual Evidence Ledger",
  },
  {
    label: "Body",
    className: "text-base text-ink-2",
    sample: "Hear what the lecture shows, not just what it says.",
  },
  {
    label: "Small",
    className: "text-sm text-muted",
    sample: "Source frame 02:14 · extracted text Week 3 · 42",
  },
  {
    label: "Mono",
    className: "font-mono text-sm text-ink-2",
    sample: "cue_012  02:15.1 → 02:17.7  2.6 s",
  },
];

export default function DesignSystemPage() {
  return (
    <main id="main" className="mx-auto w-full max-w-5xl px-6 py-14">
      <header className="flex flex-wrap items-end justify-between gap-6 border-b border-border pb-8">
        <div>
          <Logo />
          <h1 className="mt-6 text-3xl font-bold tracking-tight text-ink">
            Design system
          </h1>
          <p className="mt-2 max-w-xl text-ink-2">
            Tokens and accessible building blocks for SeeHere. Every colour pair
            shown here is tested for WCAG AA contrast, and every interactive
            component works by keyboard.
          </p>
        </div>
        <Link
          href="/"
          className="text-sm font-medium text-accent-strong underline-offset-4 hover:underline"
        >
          Back to status
        </Link>
      </header>

      <section aria-labelledby="brand" className="mt-12">
        <Eyebrow as="h2" id="brand">
          Brand
        </Eyebrow>
        <div className="mt-4 grid gap-4 sm:grid-cols-[auto_1fr]">
          <div className="flex items-center gap-4 rounded-lg border border-border bg-surface p-5 shadow-card">
            <LogoMark className="size-14" title="SeeHere logo" />
            <LogoMark className="size-8" />
          </div>
          <div className="rounded-lg border border-border bg-surface p-5 shadow-card">
            <p className="text-2xl font-semibold tracking-tight text-ink">
              <span className="text-accent-strong">“</span>Hear what the lecture
              shows, not just what it says.
              <span className="text-accent-strong">”</span>
            </p>
            <p className="mt-2 text-sm text-muted">
              Evidence-grounded audio descriptions for lecture videos.
            </p>
          </div>
        </div>
      </section>

      <section aria-labelledby="colour" className="mt-12">
        <Eyebrow as="h2" id="colour">
          Colour and contrast
        </Eyebrow>
        <ul className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {swatches.map((s) => {
            const ratio = contrastRatio(color[s.token], color[s.on]);
            return (
              <li
                key={s.name}
                className="overflow-hidden rounded-lg border border-border bg-surface shadow-card"
              >
                <div
                  className="flex h-16 items-center px-4"
                  style={{ background: color[s.on] }}
                >
                  <span
                    className="text-sm font-semibold"
                    style={{ color: color[s.token] }}
                  >
                    Aa {s.name}
                  </span>
                </div>
                <div className="px-4 py-3 text-xs">
                  <p className="font-medium text-ink">{s.usage}</p>
                  <p className="mt-1 font-mono text-muted">
                    {color[s.token]} on {color[s.on]}
                  </p>
                  <p className="mt-1 font-mono text-ink-2">
                    {ratio.toFixed(2)}:1 ·{" "}
                    {ratio >= 7 ? "AAA" : ratio >= 4.5 ? "AA" : "fails AA"}
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
      </section>

      <section aria-labelledby="type" className="mt-12">
        <Eyebrow as="h2" id="type">
          Typography · Inter and JetBrains Mono
        </Eyebrow>
        <dl className="mt-4 divide-y divide-border rounded-lg border border-border bg-surface shadow-card">
          {typeScale.map((t) => (
            <div
              key={t.label}
              className="grid items-baseline gap-2 px-5 py-4 sm:grid-cols-[120px_1fr]"
            >
              <dt className="font-mono text-xs text-muted">{t.label}</dt>
              <dd className={t.className}>{t.sample}</dd>
            </div>
          ))}
        </dl>
      </section>

      <InteractiveShowcase />
    </main>
  );
}

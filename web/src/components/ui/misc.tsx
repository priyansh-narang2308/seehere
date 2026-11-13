import { cn } from "@/lib/cn";

/** Hides content visually while keeping it available to screen readers. */
export function VisuallyHidden({ children }: { children: React.ReactNode }) {
  return <span className="sr-only">{children}</span>;
}

/** First focusable element on every page: jumps keyboard users past navigation. */
export function SkipLink({ href = "#main" }: { href?: string }) {
  return (
    <a
      href={href}
      className="sr-only rounded-md bg-ink px-4 py-2 text-sm font-medium text-white focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[70]"
    >
      Skip to main content
    </a>
  );
}

export function Kbd({ className, ...props }: React.HTMLAttributes<HTMLElement>) {
  return (
    <kbd
      className={cn(
        "inline-flex h-5 min-w-5 items-center justify-center rounded-sm border border-border-strong bg-surface px-1 font-mono text-[11px] text-ink-2 shadow-xs",
        className,
      )}
      {...props}
    />
  );
}

/**
 * Determinate progress bar with an accessible name and value text.
 * `value` is 0–100. Omit `value` for an indeterminate state.
 */
export function Progress({
  label,
  value,
  valueText,
  className,
}: {
  label: string;
  value?: number;
  valueText?: string;
  className?: string;
}) {
  const clamped = value === undefined ? undefined : Math.max(0, Math.min(100, value));
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={clamped}
      aria-valuetext={valueText ?? (clamped === undefined ? "In progress" : `${Math.round(clamped)}%`)}
      className={cn("h-1.5 w-full overflow-hidden rounded-full bg-sunken", className)}
    >
      <div
        className={cn(
          "h-full rounded-full bg-accent transition-[width] duration-300",
          clamped === undefined && "w-1/3 animate-pulse motion-reduce:animate-none",
        )}
        style={clamped === undefined ? undefined : { width: `${clamped}%` }}
      />
    </div>
  );
}

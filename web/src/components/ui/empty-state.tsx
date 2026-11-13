import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";

/** A calm, explicit "nothing here (yet)" panel. Says why, and what to do next. */
export function EmptyState({
  icon: Icon,
  title,
  description,
  children,
  headingLevel: Heading = "h2",
  className,
}: {
  icon: LucideIcon;
  title: string;
  description: React.ReactNode;
  children?: React.ReactNode;
  headingLevel?: "h2" | "h3";
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center rounded-lg border border-dashed border-border-strong bg-surface-muted px-6 py-12 text-center",
        className,
      )}
    >
      <span className="flex size-11 items-center justify-center rounded-md border border-border bg-surface text-ink-2 shadow-xs">
        <Icon aria-hidden="true" className="size-5" />
      </span>
      <Heading className="mt-4 text-base font-semibold text-ink">{title}</Heading>
      <div className="mt-1.5 max-w-md text-sm text-muted">{description}</div>
      {children && <div className="mt-6 flex flex-wrap justify-center gap-3">{children}</div>}
    </div>
  );
}

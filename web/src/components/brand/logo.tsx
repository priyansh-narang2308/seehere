import { cn } from "@/lib/cn";

/**
 * SeeHere mark: a dark tile with a blue "here" point (the visual reference) above two
 * description lines (the narration). Matches the launch visual.
 */
export function LogoMark({
  className,
  title,
}: {
  className?: string;
  title?: string;
}) {
  return (
    <svg
      viewBox="0 0 32 32"
      className={cn("size-8", className)}
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
    >
      <rect width="32" height="32" rx="8" fill="#0e1a33" />
      <circle cx="20" cy="11" r="6" fill="#2f5bff" fillOpacity="0.28" />
      <circle cx="20" cy="11" r="3.6" fill="#2f5bff" />
      <rect x="7" y="20" width="18" height="2.4" rx="1.2" fill="#ffffff" />
      <rect
        x="7"
        y="15.6"
        width="10"
        height="2.4"
        rx="1.2"
        fill="#ffffff"
        fillOpacity="0.55"
      />
    </svg>
  );
}

/** Mark + wordmark. The wordmark is real text, so it is read as "SeeHere". */
export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <LogoMark className="size-7" />
      <span className="text-[17px] font-bold tracking-tight text-ink">
        See<span className="text-accent">Here</span>
      </span>
    </span>
  );
}

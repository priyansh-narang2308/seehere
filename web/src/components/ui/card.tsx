import { cn } from "@/lib/cn";

type DivProps = React.HTMLAttributes<HTMLDivElement>;

export function Card({ className, ...props }: DivProps) {
  return (
    <div
      className={cn("rounded-lg border border-border bg-surface shadow-card", className)}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: DivProps) {
  return <div className={cn("flex flex-col gap-1 px-5 pt-5", className)} {...props} />;
}

export function CardTitle({
  className,
  as: Tag = "h3",
  ...props
}: React.HTMLAttributes<HTMLHeadingElement> & { as?: "h2" | "h3" | "h4" }) {
  return <Tag className={cn("text-base font-semibold tracking-tight text-ink", className)} {...props} />;
}

export function CardDescription({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("text-sm text-muted", className)} {...props} />;
}

export function CardContent({ className, ...props }: DivProps) {
  return <div className={cn("px-5 py-4", className)} {...props} />;
}

export function CardFooter({ className, ...props }: DivProps) {
  return (
    <div
      className={cn("flex items-center gap-3 border-t border-border px-5 py-3", className)}
      {...props}
    />
  );
}

/** Small uppercase mono label used for section eyebrows ("TRANSCRIPT", "EVIDENCE"). */
export function Eyebrow({
  className,
  as: Tag = "p",
  ...props
}: React.HTMLAttributes<HTMLElement> & { as?: "p" | "h2" | "h3" | "span" }) {
  return (
    <Tag
      className={cn("font-mono text-[11px] font-semibold tracking-[0.09em] text-muted uppercase", className)}
      {...props}
    />
  );
}

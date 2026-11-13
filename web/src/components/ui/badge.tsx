import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

export const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap [&_svg]:size-3.5",
  {
    variants: {
      tone: {
        neutral: "border-border bg-surface-muted text-ink-2",
        accent: "border-accent-line bg-accent-soft text-accent-strong",
        success: "border-success-line bg-success-soft text-success",
        warning: "border-warning-line bg-warning-soft text-warning",
        danger: "border-danger-line bg-danger-soft text-danger",
      },
      shape: {
        pill: "rounded-full",
        tag: "rounded-sm font-mono tracking-tight",
      },
    },
    defaultVariants: { tone: "neutral", shape: "pill" },
  },
);

export interface BadgeProps
  extends
    React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, shape, ...props }: BadgeProps) {
  return (
    <span
      className={cn(badgeVariants({ tone, shape }), className)}
      {...props}
    />
  );
}

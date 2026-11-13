import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "@/lib/cn";
import { Spinner } from "./spinner";

export const buttonVariants = cva(
  [
    "inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap font-medium select-none",
    "rounded-md transition-[background-color,border-color,color,box-shadow] duration-150",
    "disabled:pointer-events-none disabled:opacity-50 aria-busy:cursor-progress",
    "[&_svg]:size-4 [&_svg]:shrink-0",
  ],
  {
    variants: {
      variant: {
        primary: "bg-accent text-white shadow-xs hover:bg-accent-hover active:bg-accent-strong",
        secondary:
          "border border-border-strong bg-surface text-ink shadow-xs hover:bg-surface-muted hover:border-ink/25",
        ghost: "text-ink-2 hover:bg-sunken hover:text-ink",
        danger: "bg-danger text-white shadow-xs hover:bg-danger/90",
        link: "h-auto px-0 text-accent-strong underline-offset-4 hover:underline",
      },
      size: {
        sm: "h-8 px-3 text-sm",
        md: "h-10 px-4 text-sm",
        lg: "h-12 px-5 text-base",
        icon: "size-10",
      },
    },
    compoundVariants: [{ variant: "link", className: "h-auto px-0" }],
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  /** Render the child element (e.g. a Next.js Link) with button styling. */
  asChild?: boolean;
  /** Shows a spinner, sets aria-busy and blocks clicks. Keeps the label for screen readers. */
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, asChild = false, loading = false, disabled, children, type, ...props },
  ref,
) {
  const classes = cn(buttonVariants({ variant, size }), className);
  if (asChild) {
    return (
      <Slot ref={ref} className={classes} {...props}>
        {children}
      </Slot>
    );
  }
  return (
    <button
      ref={ref}
      type={type ?? "button"}
      className={classes}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading && <Spinner />}
      {children}
    </button>
  );
});

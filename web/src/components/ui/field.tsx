"use client";

import * as React from "react";
import { cn } from "@/lib/cn";

const controlBase = [
  "w-full rounded-md border border-border-strong bg-surface px-3 text-sm text-ink shadow-xs",
  "placeholder:text-muted transition-colors",
  "hover:border-ink/30 focus-visible:border-accent focus-visible:outline-2 focus-visible:outline-offset-0",
  "disabled:cursor-not-allowed disabled:bg-sunken disabled:opacity-70",
  "aria-invalid:border-danger aria-invalid:focus-visible:outline-danger",
].join(" ");

interface FieldContextValue {
  id: string;
  hintId?: string;
  errorId?: string;
  invalid: boolean;
  required: boolean;
}

const FieldContext = React.createContext<FieldContextValue | null>(null);

/** Hook for controls: returns the props that wire label, hint and error to the control. */
function useFieldControlProps(): Partial<React.InputHTMLAttributes<HTMLElement>> {
  const ctx = React.useContext(FieldContext);
  if (!ctx) return {};
  const describedBy = [ctx.hintId, ctx.errorId].filter(Boolean).join(" ") || undefined;
  return {
    id: ctx.id,
    "aria-describedby": describedBy,
    "aria-invalid": ctx.invalid || undefined,
    required: ctx.required || undefined,
  };
}

export interface FieldProps {
  label: React.ReactNode;
  hint?: React.ReactNode;
  error?: React.ReactNode;
  required?: boolean;
  className?: string;
  children: React.ReactNode;
}

/**
 * Accessible form field: renders a <label>, optional hint and error, and connects them to the
 * child control with id, aria-describedby and aria-invalid.
 */
export function Field({ label, hint, error, required = false, className, children }: FieldProps) {
  const id = React.useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  return (
    <FieldContext.Provider value={{ id, hintId, errorId, invalid: Boolean(error), required }}>
      <div className={cn("flex flex-col gap-1.5", className)}>
        <label htmlFor={id} className="text-sm font-medium text-ink">
          {label}
          {required && (
            <span className="ml-0.5 text-danger" aria-hidden="true">
              *
            </span>
          )}
        </label>
        {children}
        {hint && (
          <p id={hintId} className="text-xs text-muted">
            {hint}
          </p>
        )}
        {error && (
          <p id={errorId} className="text-xs font-medium text-danger">
            {error}
          </p>
        )}
      </div>
    </FieldContext.Provider>
  );
}

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...props }, ref) {
    const fieldProps = useFieldControlProps();
    return <input ref={ref} className={cn(controlBase, "h-10", className)} {...fieldProps} {...props} />;
  },
);

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(function Textarea({ className, rows = 3, ...props }, ref) {
  const fieldProps = useFieldControlProps() as React.TextareaHTMLAttributes<HTMLTextAreaElement>;
  return (
    <textarea
      ref={ref}
      rows={rows}
      className={cn(controlBase, "min-h-20 py-2 leading-relaxed", className)}
      {...fieldProps}
      {...props}
    />
  );
});

/** Checkbox with a visible label; use for confirmations such as upload rights. */
export const Checkbox = React.forwardRef<
  HTMLInputElement,
  Omit<React.InputHTMLAttributes<HTMLInputElement>, "type"> & { label: React.ReactNode }
>(function Checkbox({ className, label, id, ...props }, ref) {
  const autoId = React.useId();
  const inputId = id ?? autoId;
  return (
    <div className={cn("flex items-start gap-2.5", className)}>
      <input
        ref={ref}
        id={inputId}
        type="checkbox"
        className="mt-0.5 size-4 shrink-0 rounded-sm border-border-strong accent-accent"
        {...props}
      />
      <label htmlFor={inputId} className="text-sm leading-snug text-ink-2">
        {label}
      </label>
    </div>
  );
});

"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/cn";

/**
 * Accessible modal dialog (Radix): focus is trapped and returned to the trigger, Escape closes,
 * the title labels the dialog and the description describes it.
 */
export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

export function DialogContent({
  className,
  children,
  title,
  description,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Content> & {
  title: React.ReactNode;
  description?: React.ReactNode;
}) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-ink/40 backdrop-blur-[2px] data-[state=open]:animate-fade-in" />
      <DialogPrimitive.Content
        className={cn(
          "fixed top-1/2 left-1/2 z-50 w-[calc(100vw-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2",
          "rounded-xl border border-border bg-surface p-6 shadow-pop data-[state=open]:animate-pop-in",
          className,
        )}
        {...(description ? {} : { "aria-describedby": undefined })}
        {...props}
      >
        <div className="flex items-start justify-between gap-4">
          <DialogPrimitive.Title className="text-lg font-semibold tracking-tight text-ink">
            {title}
          </DialogPrimitive.Title>
          <DialogPrimitive.Close
            className="-m-1 rounded-md p-1 text-muted hover:bg-sunken hover:text-ink"
            aria-label="Close dialog"
          >
            <X className="size-4" aria-hidden="true" />
          </DialogPrimitive.Close>
        </div>
        {description && (
          <DialogPrimitive.Description className="mt-1.5 text-sm text-muted">
            {description}
          </DialogPrimitive.Description>
        )}
        <div className="mt-5">{children}</div>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

export function DialogFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("mt-6 flex justify-end gap-3", className)} {...props} />;
}

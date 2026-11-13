"use client";

import * as ToastPrimitive from "@radix-ui/react-toast";
import { CircleAlert, CircleCheck, Info, X } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/cn";

type ToastTone = "info" | "success" | "error";

interface ToastItem {
  id: number;
  title: string;
  description?: string;
  tone: ToastTone;
}

interface ToastApi {
  toast: (t: Omit<ToastItem, "id" | "tone"> & { tone?: ToastTone }) => void;
}

const ToastContext = React.createContext<ToastApi | null>(null);

const toneStyle: Record<ToastTone, { Icon: typeof Info; className: string }> = {
  info: { Icon: Info, className: "text-accent-strong" },
  success: { Icon: CircleCheck, className: "text-success" },
  error: { Icon: CircleAlert, className: "text-danger" },
};

/**
 * App-wide toasts (Radix Toast). Errors use an assertive live region ("foreground"); other
 * toasts are polite ("background"), so screen readers are not interrupted for routine updates.
 */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = React.useState<ToastItem[]>([]);
  const nextId = React.useRef(1);

  const api = React.useMemo<ToastApi>(
    () => ({
      toast: ({ tone = "info", ...rest }) =>
        setItems((prev) => [...prev, { id: nextId.current++, tone, ...rest }]),
    }),
    [],
  );

  return (
    <ToastContext.Provider value={api}>
      <ToastPrimitive.Provider swipeDirection="right" duration={6000}>
        {children}
        {items.map(({ id, title, description, tone }) => {
          const { Icon, className } = toneStyle[tone];
          return (
            <ToastPrimitive.Root
              key={id}
              type={tone === "error" ? "foreground" : "background"}
              onOpenChange={(open) => {
                if (!open) setItems((prev) => prev.filter((t) => t.id !== id));
              }}
              className="flex items-start gap-3 rounded-lg border border-border bg-surface p-4 shadow-pop data-[state=open]:animate-fade-in"
            >
              <Icon className={cn("mt-0.5 size-4 shrink-0", className)} aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <ToastPrimitive.Title className="text-sm font-semibold text-ink">{title}</ToastPrimitive.Title>
                {description && (
                  <ToastPrimitive.Description className="mt-0.5 text-sm text-muted">
                    {description}
                  </ToastPrimitive.Description>
                )}
              </div>
              <ToastPrimitive.Close
                aria-label="Dismiss notification"
                className="-m-1 rounded-md p-1 text-muted hover:bg-sunken hover:text-ink"
              >
                <X className="size-4" aria-hidden="true" />
              </ToastPrimitive.Close>
            </ToastPrimitive.Root>
          );
        })}
        <ToastPrimitive.Viewport
          label="Notifications ({hotkey})"
          className="fixed right-0 bottom-0 z-[60] flex w-full max-w-sm flex-col gap-2 p-4 outline-none"
        />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = React.useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  return ctx;
}

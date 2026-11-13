"use client";

import * as TabsPrimitive from "@radix-ui/react-tabs";
import * as React from "react";
import { cn } from "@/lib/cn";

/** Accessible tabs (Radix): arrow keys move between tabs, Home/End jump, panels are labelled. */
export const Tabs = TabsPrimitive.Root;

export function TabsList({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn("inline-flex items-center gap-1 rounded-md border border-border bg-sunken p-1", className)}
      {...props}
    />
  );
}

export function TabsTrigger({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        "rounded-sm px-3 py-1.5 text-sm font-medium text-ink-2 transition-colors",
        "hover:text-ink data-[state=active]:bg-surface data-[state=active]:text-ink data-[state=active]:shadow-xs",
        className,
      )}
      {...props}
    />
  );
}

export function TabsContent({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return <TabsPrimitive.Content className={cn("mt-4", className)} {...props} />;
}

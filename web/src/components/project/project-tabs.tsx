"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";
import { isActivePath } from "@/lib/navigation";

/** Section links for one project. Links (not ARIA tabs) because each section is its own page. */
export function ProjectTabs({ projectId }: { projectId: string }) {
  const pathname = usePathname();
  const items = [
    { href: `/projects/${projectId}/processing`, label: "Processing" },
    { href: `/projects/${projectId}/results`, label: "Results" },
  ];
  return (
    <nav aria-label="Project sections" className="border-b border-border">
      <ul className="-mb-px flex gap-6">
        {items.map((item) => {
          const active = isActivePath(pathname, item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "inline-block rounded-t-sm border-b-2 px-0.5 pb-3 text-sm font-medium transition-colors",
                  active ? "border-accent text-ink" : "border-transparent text-muted hover:border-border-strong hover:text-ink",
                )}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

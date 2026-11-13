"use client";

import { Menu, Upload, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { isActivePath, primaryNav, uploadNav } from "@/lib/navigation";

/** Reads the current path. Must sit inside <Suspense> (see SiteHeader). */
export function MainNav() {
  return <MainNavView pathname={usePathname()} />;
}

/**
 * Header navigation. Wide screens: inline links plus the upload button.
 * Narrow screens: a disclosure menu (button with aria-expanded/aria-controls).
 * `pathname` is null while the path is unknown (Suspense fallback); nothing is marked current then.
 */
export function MainNavView({ pathname }: { pathname: string | null }) {
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const toggleRef = useRef<HTMLButtonElement>(null);

  // Close the mobile menu whenever the route changes. Adjusting state during render (rather
  // than in an effect) is React's recommended way to reset state when a prop changes.
  const [lastPath, setLastPath] = useState(pathname);
  if (pathname !== lastPath) {
    setLastPath(pathname);
    setOpen(false);
  }

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        toggleRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);

  const uploadActive = isActivePath(pathname, uploadNav.href);

  return (
    <>
      <nav aria-label="Main" className="hidden items-center gap-1 sm:flex">
        <ul className="flex items-center gap-1">
          {primaryNav.map((item) => {
            const active = isActivePath(pathname, item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    active ? "bg-sunken text-ink" : "text-ink-2 hover:bg-sunken hover:text-ink",
                  )}
                >
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
        <Button asChild size="sm" className="ml-2">
          <Link href={uploadNav.href} aria-current={uploadActive ? "page" : undefined}>
            <Upload aria-hidden="true" />
            {uploadNav.label}
          </Link>
        </Button>
      </nav>

      <div className="sm:hidden">
        <Button
          ref={toggleRef}
          variant="ghost"
          size="icon"
          aria-expanded={open}
          aria-controls={menuId}
          onClick={() => setOpen((o) => !o)}
        >
          {open ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
          <span className="sr-only">{open ? "Close menu" : "Open menu"}</span>
        </Button>
      </div>

      <nav
        id={menuId}
        aria-label="Main"
        hidden={!open}
        className="absolute inset-x-0 top-full border-b border-border bg-surface shadow-card sm:hidden"
      >
        <ul className="flex flex-col p-2">
          {[...primaryNav, uploadNav].map((item) => {
            const active = isActivePath(pathname, item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  onClick={() => setOpen(false)}
                  className={cn(
                    "block rounded-md px-3 py-3 text-base font-medium",
                    active ? "bg-sunken text-ink" : "text-ink-2 hover:bg-sunken hover:text-ink",
                  )}
                >
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </>
  );
}

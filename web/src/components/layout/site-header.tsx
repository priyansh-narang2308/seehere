import Link from "next/link";
import { Suspense } from "react";
import { Logo } from "@/components/brand/logo";
import { MainNav, MainNavView } from "./main-nav";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-canvas/90 backdrop-blur supports-[backdrop-filter]:bg-canvas/80">
      <div className="relative mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <Link
          href="/"
          className="-m-1 rounded-md p-1"
          aria-label="SeeHere home"
        >
          <Logo />
        </Link>
        {/* The pathname is unknown while prerendering dynamic routes, so render links without
            a current page until it resolves (Next.js Cache Components requirement). */}
        <Suspense fallback={<MainNavView pathname={null} />}>
          <MainNav />
        </Suspense>
      </div>
    </header>
  );
}

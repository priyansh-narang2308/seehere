import Link from "next/link";
import { BackendStatus } from "@/components/BackendStatus";
import { Logo } from "@/components/brand/logo";
import { Badge } from "@/components/ui/badge";

export default function Home() {
  return (
    <main
      id="main"
      className="flex flex-1 flex-col items-center gap-10 px-6 py-20"
    >
      <header className="w-full max-w-xl">
        <div className="flex items-center justify-between">
          <Logo />
          <Badge tone="warning">Development build</Badge>
        </div>
        <h1 className="mt-10 text-4xl font-bold tracking-tight text-ink">
          Hear what the lecture shows, not just what it says.
        </h1>
        <p className="mt-3 text-lg text-ink-2">
          Evidence-grounded audio descriptions for lecture videos.
        </p>
        <Link
          href="/design"
          className="mt-4 inline-block text-sm font-medium text-accent-strong underline-offset-4 hover:underline"
        >
          View the design system
        </Link>
      </header>
      <BackendStatus />
    </main>
  );
}

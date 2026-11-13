import { type NextRequest, NextResponse } from "next/server";
import { isUuid } from "@/lib/ids";

/**
 * Rejects malformed project IDs before rendering starts, so they get a real 404 status.
 * (The layout's notFound() runs after the prerendered shell has streamed, when the status is
 * already 200; it still renders the not-found UI as a second line of defence.)
 */
export function proxy(request: NextRequest) {
  const projectId = request.nextUrl.pathname.split("/")[2] ?? "";
  if (!isUuid(projectId)) {
    // Rewriting to a path with no route renders app/not-found.tsx with status 404.
    return NextResponse.rewrite(new URL("/__not-found", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: "/projects/:projectId/:path*",
};

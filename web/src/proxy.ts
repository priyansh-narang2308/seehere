import { type NextRequest, NextResponse } from "next/server";
import { SERVER_API_BASE } from "@/lib/api";
import { isUuid } from "@/lib/ids";

/**
 * Gives unknown projects a real 404 status before rendering starts.
 *
 * The project layout's notFound() runs after the prerendered shell has streamed, when the status
 * is already 200, so it is only a second line of defence. Here we reject malformed IDs outright,
 * and ask the API whether a well-formed ID exists. If the API cannot answer (down, slow), the
 * request continues and the page's error boundary reports the outage instead of a false 404.
 */
export async function proxy(request: NextRequest) {
  const projectId = request.nextUrl.pathname.split("/")[2] ?? "";
  if (!isUuid(projectId) || (await projectIsMissing(projectId))) {
    // Rewriting to a path with no route renders app/not-found.tsx with status 404.
    return NextResponse.rewrite(new URL("/__not-found", request.url));
  }
  return NextResponse.next();
}

async function projectIsMissing(projectId: string): Promise<boolean> {
  if (!SERVER_API_BASE) return false;
  try {
    const res = await fetch(`${SERVER_API_BASE}/api/projects/${projectId}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    return res.status === 404;
  } catch {
    return false;
  }
}

export const config = {
  matcher: "/projects/:projectId/:path*",
};

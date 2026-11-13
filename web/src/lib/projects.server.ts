import "server-only";
import { cache } from "react";
import { ApiError, getJson, SERVER_API_BASE, type Project } from "@/lib/api";
import { isUuid } from "@/lib/ids";

/**
 * Load one project on the server. Returns null when it does not exist (or the ID is malformed),
 * so callers can render notFound(). Other failures (API down) throw to the error boundary.
 * Wrapped in React cache() so the layout and page share one request per render.
 */
export const getProject = cache(async (projectId: string): Promise<Project | null> => {
  if (!isUuid(projectId)) return null;
  try {
    return await getJson<Project>(`/api/projects/${projectId}`, undefined, SERVER_API_BASE);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
});

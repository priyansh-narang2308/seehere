// @vitest-environment node
import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({ SERVER_API_BASE: "http://api.test" }));
const { proxy } = await import("./proxy");

const id = "0b8f7c1e-1d2a-4c3b-9e8f-7a6b5c4d3e2f";
const run = (path: string) => proxy(new NextRequest(`http://localhost:3000${path}`));
const rewrittenTo = (res: Response) => res.headers.get("x-middleware-rewrite");

afterEach(() => vi.unstubAllGlobals());

describe("project proxy", () => {
  it("rewrites malformed IDs to not-found without calling the API", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    expect(rewrittenTo(await run("/projects/not-a-uuid/processing"))).toMatch(/\/__not-found$/);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("rewrites well-formed IDs the API does not know", async () => {
    const fetch = vi.fn(async () => new Response(null, { status: 404 }));
    vi.stubGlobal("fetch", fetch);
    expect(rewrittenTo(await run(`/projects/${id}/results`))).toMatch(/\/__not-found$/);
    expect(fetch).toHaveBeenCalledWith(`http://api.test/api/projects/${id}`, expect.anything());
  });

  it("lets existing projects through", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ id })));
    expect(rewrittenTo(await run(`/projects/${id}/processing`))).toBeNull();
  });

  it("lets the request through when the API cannot answer, so the outage is reported honestly", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("down"))));
    expect(rewrittenTo(await run(`/projects/${id}/processing`))).toBeNull();
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 500 })));
    expect(rewrittenTo(await run(`/projects/${id}/processing`))).toBeNull();
  });
});

import { connection } from "next/server";

// Liveness for the web container (Caddy/Docker health checks). Runs per request.
export async function GET() {
  await connection();
  return Response.json({
    status: "ok",
    service: "web",
    time: new Date().toISOString(),
  });
}

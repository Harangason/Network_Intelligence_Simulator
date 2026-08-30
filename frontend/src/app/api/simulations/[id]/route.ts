import { NextResponse } from "next/server";
import { getDevJob } from "../../_dev-opt/store";
import { proxyBackend } from "../../_backend";

// DEV-OPT: local/v0 in-memory job lookup; production requests are handled by Flask.
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const backend = await proxyBackend(`/simulations/${encodeURIComponent(id)}`, {
    headers: { "X-Project-ID": request.headers.get("X-Project-ID") ?? "default" },
  });
  if (backend && backend.status !== 404) return backend;
  const job = getDevJob(id);
  return job
    ? NextResponse.json(job)
    : NextResponse.json({ error: "Simulation nicht gefunden." }, { status: 404 });
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const backend = await proxyBackend(`/simulations/${encodeURIComponent(id)}/cancel`, {
    method: "POST",
    body: "{}",
    headers: { "X-Project-ID": request.headers.get("X-Project-ID") ?? "default" },
  });
  return backend ?? NextResponse.json({ error: "Simulationsdienst nicht erreichbar." }, { status: 503 });
}

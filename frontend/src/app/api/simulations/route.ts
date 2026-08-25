import { NextRequest, NextResponse } from "next/server";
import { createDevJob, listDevJobs } from "../_dev-opt/store";
import { proxyBackend } from "../_backend";

// DEV-OPT: local/v0 simulation fallback; production requests are handled by Flask.
export async function POST(request: NextRequest) {
  const payload: unknown = await request.json().catch(() => null);
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return NextResponse.json({ error: "Ein JSON-Objekt wird erwartet." }, { status: 400 });
  }
  const backend = await proxyBackend("/simulations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (backend) return backend;
  if ((payload as Record<string, unknown>).workflow_managed) {
    return NextResponse.json({ error: "Der Snapshot-Simulationsdienst ist nicht erreichbar." }, { status: 503 });
  }
  return NextResponse.json(createDevJob(payload as Record<string, unknown>, false), { status: 202 });
}

export async function GET() {
  const backend = await proxyBackend("/simulations");
  return backend ?? NextResponse.json({ jobs: listDevJobs() });
}

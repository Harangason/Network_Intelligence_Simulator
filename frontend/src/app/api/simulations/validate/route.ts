import { NextRequest, NextResponse } from "next/server";
import { createDevJob } from "../../_dev-opt/store";
import { proxyBackend } from "../../_backend";

// DEV-OPT: local/v0 validation fallback; production requests are handled by Flask.
export async function POST(request: NextRequest) {
  const payload: unknown = await request.json().catch(() => null);
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return NextResponse.json({ error: "Ein JSON-Objekt wird erwartet." }, { status: 400 });
  }
  const backend = await proxyBackend("/simulations/validate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return backend ?? NextResponse.json(createDevJob(payload as Record<string, unknown>, true), { status: 202 });
}

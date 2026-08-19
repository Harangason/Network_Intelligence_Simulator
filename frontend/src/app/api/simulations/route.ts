import { NextRequest, NextResponse } from "next/server";
import { createDevJob } from "../_dev-opt/store";

// DEV-OPT: local/v0 simulation fallback; production requests are handled by Flask.
export async function POST(request: NextRequest) {
  const payload: unknown = await request.json().catch(() => null);
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return NextResponse.json({ error: "Ein JSON-Objekt wird erwartet." }, { status: 400 });
  }
  return NextResponse.json(createDevJob(payload as Record<string, unknown>, false), { status: 202 });
}

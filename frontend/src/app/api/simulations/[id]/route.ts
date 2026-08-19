import { NextResponse } from "next/server";
import { getDevJob } from "../../_dev-opt/store";

// DEV-OPT: local/v0 in-memory job lookup; production requests are handled by Flask.
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const job = getDevJob(id);
  return job
    ? NextResponse.json(job)
    : NextResponse.json({ error: "Simulation nicht gefunden." }, { status: 404 });
}

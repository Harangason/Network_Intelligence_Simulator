import { NextResponse } from "next/server";
import { devCatalog } from "../_dev-opt/store";
import { proxyBackend } from "../_backend";

// DEV-OPT: v0 runs the frontend without the Python service. In Vercel Services,
// the /api prefix is owned by Flask and this Next.js fallback is bypassed.
export async function GET() {
  const backend = await proxyBackend("/technologies");
  if (backend) return backend;
  return NextResponse.json(devCatalog);
}

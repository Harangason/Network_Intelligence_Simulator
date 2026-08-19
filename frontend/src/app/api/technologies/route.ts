import { NextResponse } from "next/server";
import { devCatalog } from "../_dev-opt/store";

// DEV-OPT: v0 runs the frontend without the Python service. In Vercel Services,
// the /api prefix is owned by Flask and this Next.js fallback is bypassed.
export function GET() {
  return NextResponse.json(devCatalog);
}

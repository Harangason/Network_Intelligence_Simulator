import "server-only";

import type { SimulationJob } from "@/lib/types";
import {
  deleteProgramCache,
  pruneProgramCache,
  readProgramCache,
  writeProgramCache,
} from "@/lib/server/program-cache";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const CACHE_NAMESPACE = "simulation-jobs";
const MAX_JOB_BYTES = 1_000_000;
const MAX_JOBS = 30;
const CACHE_TTL_MS = 2 * 60 * 60 * 1000;

function isSimulationJob(value: unknown): value is SimulationJob {
  if (!value || typeof value !== "object") return false;
  const job = value as Partial<SimulationJob>;
  return typeof job.id === "string" && typeof job.status === "string";
}

function noStore(payload: unknown, init?: ResponseInit) {
  return Response.json(payload, {
    ...init,
    headers: { ...init?.headers, "Cache-Control": "no-store" },
  });
}

export async function GET(request: Request) {
  const id = new URL(request.url).searchParams.get("id")?.trim();
  if (!id) return noStore({ error: "id fehlt." }, { status: 400 });
  const entry = await readProgramCache<SimulationJob>(CACHE_NAMESPACE, id);
  if (!entry || !isSimulationJob(entry.value)) {
    return noStore({ error: "Simulationslauf nicht im Programm-Cache gefunden." }, { status: 404 });
  }
  return noStore(entry.value);
}

export async function PUT(request: Request) {
  const payload = await request.json().catch(() => null);
  if (!isSimulationJob(payload) || !payload.id.startsWith("local-")) {
    return noStore({ error: "Ungueltiger lokaler Simulationslauf." }, { status: 400 });
  }
  await writeProgramCache(CACHE_NAMESPACE, payload.id, payload, MAX_JOB_BYTES, CACHE_TTL_MS);
  await pruneProgramCache(CACHE_NAMESPACE, MAX_JOBS);
  return noStore({ ok: true, id: payload.id });
}

export async function DELETE(request: Request) {
  const id = new URL(request.url).searchParams.get("id")?.trim();
  if (!id?.startsWith("local-")) return noStore({ error: "Ungueltige id." }, { status: 400 });
  await deleteProgramCache(CACHE_NAMESPACE, id);
  return noStore({ ok: true });
}

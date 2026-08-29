import "server-only";

import { execFile } from "node:child_process";
import { appendFile, mkdir } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const execFileAsync = promisify(execFile);
const LOG_FILES = {
  error: "agent-errors.txt",
  performance: "agent-performance.txt",
  question: "agent-questions.txt",
  workflow: "workflow-status.txt",
} as const;

type DiagnosticCategory = keyof typeof LOG_FILES;
type CpuTimes = { idle: number; total: number };

function projectRoot() {
  return path.basename(process.cwd()).toLowerCase() === "frontend"
    ? path.dirname(process.cwd())
    : process.cwd();
}

function diagnosticsDirectory() {
  return path.join(projectRoot(), "backend", "runtime", "agent-diagnostics");
}

function oneLine(value: unknown, maximum = 4000) {
  const serialized = typeof value === "string" ? value : JSON.stringify(value ?? {});
  return serialized.replace(/[\r\n\t]+/g, " ").replace(/\s+/g, " ").trim().slice(0, maximum);
}

function safeToken(value: unknown, fallback: string) {
  const normalized = String(value ?? "").trim().replace(/[^a-zA-Z0-9._-]+/g, "-").slice(0, 120);
  return normalized || fallback;
}

async function appendDiagnostic(
  category: DiagnosticCategory,
  input: { projectId?: unknown; runId?: unknown; step?: unknown; event?: unknown; details?: unknown },
) {
  const directory = diagnosticsDirectory();
  await mkdir(directory, { recursive: true });
  await Promise.all(Object.values(LOG_FILES).map((file) => appendFile(path.join(directory, file), "", "utf8")));
  const line = [
    new Date().toISOString(),
    `project=${safeToken(input.projectId, "default")}`,
    `run=${safeToken(input.runId, "none")}`,
    `step=${safeToken(input.step, "unknown")}`,
    `event=${safeToken(input.event, category)}`,
    `details=${oneLine(input.details)}`,
  ].join("\t");
  await appendFile(path.join(directory, LOG_FILES[category]), `${line}\n`, "utf8");
}

function cpuTimes(): CpuTimes {
  return os.cpus().reduce(
    (result, cpu) => {
      const total = Object.values(cpu.times).reduce((sum, value) => sum + value, 0);
      return { idle: result.idle + cpu.times.idle, total: result.total + total };
    },
    { idle: 0, total: 0 },
  );
}

async function cpuPercent() {
  const before = cpuTimes();
  await new Promise((resolve) => setTimeout(resolve, 120));
  const after = cpuTimes();
  const total = Math.max(1, after.total - before.total);
  const idle = Math.max(0, after.idle - before.idle);
  return Number((100 * (1 - idle / total)).toFixed(1));
}

async function gpuSample() {
  try {
    const { stdout } = await execFileAsync(
      "nvidia-smi",
      ["--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
      { timeout: 1800, windowsHide: true },
    );
    const [utilization, memoryUsed, memoryTotal] = stdout.trim().split(/\r?\n/, 1)[0].split(",").map((value) => Number(value.trim()));
    if (![utilization, memoryUsed, memoryTotal].every(Number.isFinite)) return null;
    return {
      utilization_percent: utilization,
      memory_used_mb: memoryUsed,
      memory_total_mb: memoryTotal,
    };
  } catch {
    return null;
  }
}

async function ollamaSample() {
  try {
    const response = await fetch("http://127.0.0.1:11434/api/ps", {
      cache: "no-store",
      signal: AbortSignal.timeout(1500),
    });
    if (!response.ok) return [];
    const payload = await response.json() as { models?: Array<Record<string, unknown>> };
    return (payload.models ?? []).slice(0, 4).map((model) => ({
      name: String(model.name ?? model.model ?? "unknown"),
      size_mb: Math.round(Number(model.size ?? 0) / 1024 / 1024),
      vram_mb: Math.round(Number(model.size_vram ?? 0) / 1024 / 1024),
    }));
  } catch {
    return [];
  }
}

async function performanceSample() {
  const [cpu, gpu, ollama] = await Promise.all([cpuPercent(), gpuSample(), ollamaSample()]);
  const totalMemory = os.totalmem();
  const usedMemory = totalMemory - os.freemem();
  return {
    cpu_percent: cpu,
    memory_percent: Number((usedMemory / Math.max(1, totalMemory) * 100).toFixed(1)),
    memory_used_mb: Math.round(usedMemory / 1024 / 1024),
    memory_total_mb: Math.round(totalMemory / 1024 / 1024),
    frontend_rss_mb: Math.round(process.memoryUsage().rss / 1024 / 1024),
    gpu,
    ollama,
  };
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const sample = await performanceSample();
  await appendDiagnostic("performance", {
    projectId: url.searchParams.get("projectId"),
    runId: url.searchParams.get("runId"),
    step: url.searchParams.get("step"),
    event: "sample",
    details: sample,
  });
  return Response.json(sample, { headers: { "Cache-Control": "no-store" } });
}

export async function POST(request: Request) {
  const payload = await request.json().catch(() => null) as Record<string, unknown> | null;
  const category = String(payload?.category ?? "") as DiagnosticCategory;
  if (!payload || !Object.hasOwn(LOG_FILES, category)) {
    return Response.json({ error: "Unbekannte Diagnosekategorie." }, { status: 400 });
  }
  await appendDiagnostic(category, {
    projectId: payload.projectId,
    runId: payload.runId,
    step: payload.step,
    event: payload.event,
    details: payload.details,
  });
  return Response.json({ ok: true, file: LOG_FILES[category] });
}

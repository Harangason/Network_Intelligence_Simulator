import "server-only";

import { execFile } from "node:child_process";
import os from "node:os";
import { promisify } from "node:util";
import {
  appendAgentDiagnostic,
  AGENT_DIAGNOSTIC_LOG_FILES,
  agentDiagnosticsFilePath,
  agentEventLoggingEnabled,
  setAgentEventLoggingEnabled,
  type AgentDiagnosticCategory,
} from "@/lib/agent/agent-diagnostics-log";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const execFileAsync = promisify(execFile);
type CpuTimes = { idle: number; total: number };
type GpuSample = { utilization_percent: number; memory_used_mb: number; memory_total_mb: number };
type HostPerformanceSample = {
  source: "windows-host";
  sampled_at: string;
  cpu_percent: number;
  memory_percent: number;
  memory_used_mb: number;
  memory_total_mb: number;
  gpu: GpuSample | null;
};

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

function finiteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

async function hostPerformanceSample(): Promise<HostPerformanceSample | null> {
  const url = process.env.NETWORKIS_HOST_METRICS_URL?.trim();
  if (!url) return null;
  try {
    const response = await fetch(url, { cache: "no-store", signal: AbortSignal.timeout(1200) });
    if (!response.ok) return null;
    const payload = await response.json() as Partial<HostPerformanceSample>;
    if (
      payload.source !== "windows-host"
      || typeof payload.sampled_at !== "string"
      || !finiteNumber(payload.cpu_percent)
      || !finiteNumber(payload.memory_percent)
      || !finiteNumber(payload.memory_used_mb)
      || !finiteNumber(payload.memory_total_mb)
    ) return null;
    const gpu = payload.gpu;
    if (gpu !== null && gpu !== undefined && (
      !finiteNumber(gpu.utilization_percent)
      || !finiteNumber(gpu.memory_used_mb)
      || !finiteNumber(gpu.memory_total_mb)
    )) return null;
    return { ...payload, gpu: gpu ?? null } as HostPerformanceSample;
  } catch {
    return null;
  }
}

async function ollamaSample() {
  try {
    const baseUrl = (process.env.LOCAL_AI_BASE_URL ?? "http://127.0.0.1:11434/v1")
      .replace(/\/$/, "")
      .replace(/\/v1$/, "");
    const response = await fetch(`${baseUrl}/api/ps`, {
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
  const [host, ollama] = await Promise.all([hostPerformanceSample(), ollamaSample()]);
  const [runtimeCpu, runtimeGpu] = host ? [null, null] : await Promise.all([cpuPercent(), gpuSample()]);
  const runtimeTotalMemory = os.totalmem();
  const runtimeUsedMemory = runtimeTotalMemory - os.freemem();
  const totalMemory = host ? host.memory_total_mb * 1024 * 1024 : runtimeTotalMemory;
  const usedMemory = host ? host.memory_used_mb * 1024 * 1024 : runtimeUsedMemory;
  const aiProvider = process.env.AI_PROVIDER ?? "hybrid-demand";
  const localAiModel = process.env.LOCAL_AI_MODEL ?? "qwen3.8:27b";
  const localAiFastModel = process.env.LOCAL_AI_FAST_MODEL ?? "llama3.1:8b";
  return {
    source: host ? "windows-host" : "container-runtime",
    sampled_at: host?.sampled_at ?? new Date().toISOString(),
    host_metrics_available: Boolean(host),
    cpu_percent: host?.cpu_percent ?? runtimeCpu ?? 0,
    memory_percent: host?.memory_percent ?? Number((usedMemory / Math.max(1, totalMemory) * 100).toFixed(1)),
    memory_used_mb: Math.round(usedMemory / 1024 / 1024),
    memory_total_mb: Math.round(totalMemory / 1024 / 1024),
    frontend_rss_mb: Math.round(process.memoryUsage().rss / 1024 / 1024),
    gpu: host?.gpu ?? runtimeGpu,
    ollama,
    ai: {
      provider: aiProvider,
      local_model: localAiModel,
      local_fast_model: localAiFastModel,
      local_model_loaded: ollama.some((model) => model.name === localAiModel || model.name.replace(/:latest$/, "") === localAiModel.replace(/:latest$/, "")),
    },
  };
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  if (url.searchParams.get("agentLog") === "status") {
    return Response.json({
      enabled: await agentEventLoggingEnabled(),
      file: agentDiagnosticsFilePath("agent"),
    }, { headers: { "Cache-Control": "no-store" } });
  }
  const sample = await performanceSample();
  await appendAgentDiagnostic("performance", {
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
  if (payload?.action === "agent-log") {
    const enabled = payload.enabled === true;
    if (!enabled) {
      await appendAgentDiagnostic("agent", {
        projectId: payload.projectId,
        runId: payload.runId,
        step: "agent-log",
        event: "agent-event-log-disabled",
        details: { source: "topbar" },
      });
    }
    const state = await setAgentEventLoggingEnabled(enabled);
    if (enabled) {
      await appendAgentDiagnostic("agent", {
        projectId: payload.projectId,
        runId: payload.runId,
        step: "agent-log",
        event: "agent-event-log-enabled",
        details: { source: "topbar" },
      });
    }
    return Response.json({ ok: true, ...state }, { headers: { "Cache-Control": "no-store" } });
  }
  const category = String(payload?.category ?? "") as AgentDiagnosticCategory;
  if (!payload || !Object.hasOwn(AGENT_DIAGNOSTIC_LOG_FILES, category)) {
    return Response.json({ error: "Unbekannte Diagnosekategorie." }, { status: 400 });
  }
  await appendAgentDiagnostic(category, {
    projectId: payload.projectId,
    runId: payload.runId,
    step: payload.step,
    event: payload.event,
    details: payload.details,
  });
  return Response.json({ ok: true, file: AGENT_DIAGNOSTIC_LOG_FILES[category] });
}

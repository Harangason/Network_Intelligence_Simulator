import "server-only";

import {
  createEngineeringWorkload,
  getEngineeringWorkloadObjects,
  startEngineeringWorkload,
} from "@/lib/engineering-server-client";

export type SignalBatchDomain = "thermal" | "motion";

export type SignalBatchTarget = {
  count: number;
  domain: SignalBatchDomain;
  requestedTarget: string;
};

export type SignalBatchRequest = {
  targets: SignalBatchTarget[];
  total: number;
};

const MAX_BATCH_SIGNALS = 100;

function normalized(value: unknown) {
  return String(value ?? "")
    .toLowerCase()
    .replace(/ae/g, "a")
    .replace(/oe/g, "o")
    .replace(/ue/g, "u")
    .replace(/[ä]/g, "a")
    .replace(/[ö]/g, "o")
    .replace(/[ü]/g, "u")
    .replace(/[^a-z0-9]+/g, "")
    .trim();
}

function targetDomain(value: string): SignalBatchDomain | null {
  const key = normalized(value);
  if (key.includes("motion") || key.includes("bewegung") || key.includes("dynamik")) return "motion";
  if (key.includes("thermal") || key.includes("temperatur") || key.includes("temperature")) return "thermal";
  return null;
}

export function extractSignalBatchRequest(text: string): SignalBatchRequest | null {
  if (!/\bsignale?\b/i.test(text)) return null;
  if (!/\b(anleg(?:e|en|t)|erzeug(?:e|en|t)|erstell(?:e|en|t)|hinzuf(?:u|ue|ü)g(?:e|en|t)|erg[aä]nz(?:e|en|t)|generier(?:e|en|t))\b/i.test(text)) return null;

  const targets = new Map<SignalBatchDomain, SignalBatchTarget>();
  const patterns = [
    /(\d{1,3})\s*(?:weitere\s+)?(?:signale?\s*)?f(?:u|ue|ü)r\s+(?:(?:die|den|das)\s+)?([\p{L}\d_-]+)/giu,
    /(\d{1,3})\s+(?:signale?\s*)?(temperatur|temperature|thermal|motion|bewegung|dynamik)\b/giu,
    /(temperatur|temperature|thermal|motion|bewegung|dynamik)\s*[:=]\s*(\d{1,3})\b/giu,
  ];
  patterns.forEach((pattern, patternIndex) => {
    for (const match of text.matchAll(pattern)) {
      const count = Number(patternIndex === 2 ? match[2] : match[1]);
      const requestedTarget = String(patternIndex === 2 ? match[1] : match[2]).trim();
      const domain = targetDomain(requestedTarget);
      if (!domain || !Number.isInteger(count) || count <= 0) continue;
      const previous = targets.get(domain);
      targets.set(domain, {
        count: Math.max(previous?.count ?? 0, count),
        domain,
        requestedTarget: previous ? `${previous.requestedTarget}, ${requestedTarget}` : requestedTarget,
      });
    }
  });

  const result = [...targets.values()];
  const packageTotal = result.reduce((sum, target) => sum + target.count, 0);
  const explicitTotalMatch = text.match(/\b(?:insgesamt|gesamt|total)\s*[:=]?\s*(\d{1,3})\b/i);
  const total = explicitTotalMatch ? Number(explicitTotalMatch[1]) : packageTotal;
  if (!result.length || total <= 0 || total > MAX_BATCH_SIGNALS) return null;
  return { targets: result, total };
}

export function isBulkSignalCreationRequest(text: string) {
  return extractSignalBatchRequest(text) !== null;
}

export async function registerEngineeringSignalBatch(text: string) {
  const request = extractSignalBatchRequest(text);
  if (!request) throw new Error("Der Signalauftrag enthaelt keine eindeutig zuordenbaren Mengen und Ziele.");
  const workload = await createEngineeringWorkload({
    prompt: text,
    title: `Generate ${request.total} Engineering Signals`,
    description: text,
    workload_type: "SIGNAL_GENERATION",
    target_object: "Signal",
    requested_total: request.total,
    max_generation_attempts: 3,
    created_by: "engineering-chat-agent",
    agent: "engineering-agent",
    model: "engineering-workload-orchestrator-v1",
    work_packages: request.targets.map((target) => ({
      category: target.domain,
      requested_count: target.count,
      configuration: { requested_target: target.requestedTarget },
    })),
  });
  const workloadId = String(workload.workload_id ?? "");
  if (!workloadId) throw new Error("Der Workload besitzt keine ID.");
  const executed = await startEngineeringWorkload(workloadId);
  const objects = await getEngineeringWorkloadObjects(workloadId);
  const packages = Array.isArray(executed.work_packages) ? executed.work_packages as Record<string, unknown>[] : [];
  const dependencies = Array.isArray(executed.dependencies_resolved) ? executed.dependencies_resolved as Record<string, unknown>[] : [];
  const status = String(executed.status ?? "FAILED");
  return {
    status,
    workload_id: workloadId,
    requested: Number(executed.requested_total ?? request.total),
    generated: Number(executed.generated_count ?? 0),
    valid: Number(executed.valid_count ?? 0),
    invalid: Number(executed.invalid_count ?? 0),
    duplicates: Number(executed.duplicate_count ?? 0),
    missing: Number(executed.missing_count ?? request.total),
    attempts: Number(executed.attempts ?? 0),
    max_generation_attempts: Number(executed.max_generation_attempts ?? 3),
    ready_for_review: status === "READY_FOR_REVIEW",
    task_complete: status === "COMPLETED",
    work_packages: packages.map((item) => ({
      work_package_id: item.work_package_id,
      package_code: item.package_code,
      category: item.category,
      requested: item.requested_count,
      generated: item.generated_count,
      valid: item.valid_count,
      invalid: item.invalid_count,
      duplicates: item.duplicate_count,
      missing: item.missing_count,
      status: item.status,
      findings: item.findings,
    })),
    dependencies: dependencies.map((item) => ({
      workload_id: item.dependency_workload_id,
      title: item.title,
      type: item.workload_type,
      status: item.status,
      required_status: item.required_status,
      satisfied: item.satisfied,
    })),
    proposal_count: new Set(objects.items.map((item) => String(item.proposal_id ?? "")).filter(Boolean)).size,
    objects_count: objects.count,
    review_required: status === "READY_FOR_REVIEW" || status === "BLOCKED",
    note: status === "READY_FOR_REVIEW"
      ? "Alle Completion Criteria sind strukturiert erfuellt. Die Proposal-Objekte warten auf menschliche Freigabe."
      : status === "BLOCKED"
        ? "Der Workload wartet auf eine explizite Dependency-Freigabe oder fachliche Ergaenzung."
        : "Generator-Success wurde nicht als Workload-Completion gewertet.",
  };
}

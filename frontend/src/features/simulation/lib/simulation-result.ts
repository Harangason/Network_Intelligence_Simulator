import type { SimulationJob } from "../../../shared/api/types";

type PersistedSimulation = {
  id: string;
  job_id?: string | null;
  created_at: string;
  is_outdated: boolean;
};

/** Compact refreshes update status/provenance without dropping frozen details. */
export function mergeSimulationSnapshots<T extends PersistedSimulation>(summaries: T[], cached: T[]): T[] {
  const details = new Map(cached.map((item) => [item.id, item]));
  return summaries.map((item) => ({ ...details.get(item.id), ...item }));
}

/** Resolve only records returned by the current project's snapshot endpoint. */
export function selectSimulationSnapshot<T extends PersistedSimulation>(
  snapshots: T[],
  selection: { snapshotId?: string; jobId?: string } = {},
): T | null {
  if (selection.snapshotId) {
    const selected = snapshots.find((item) => item.id === selection.snapshotId);
    if (!selected?.job_id) throw new Error("Dieser Simulationslauf ist in diesem Projekt nicht verfügbar.");
    return selected;
  }
  if (selection.jobId) return snapshots.find((item) => item.job_id === selection.jobId) ?? null;
  const executed = snapshots.filter((item) => item.job_id);
  const current = executed.filter((item) => !item.is_outdated);
  return [...(current.length ? current : executed)].sort((a, b) => b.created_at.localeCompare(a.created_at))[0] ?? null;
}

/** Job registries contain summaries; snapshot details retain the runtime data. */
export function mergeSimulationResult(
  jobResult: SimulationJob["result"] | undefined,
  snapshotResult: SimulationJob["result"] | undefined,
): SimulationJob["result"] | undefined {
  if (!jobResult) return snapshotResult;
  if (!snapshotResult) return jobResult;
  return { ...snapshotResult, ...jobResult };
}

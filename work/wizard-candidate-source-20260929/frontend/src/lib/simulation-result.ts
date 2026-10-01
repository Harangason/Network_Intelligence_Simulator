import type { SimulationJob } from "./types";

/** Job registries contain summaries; snapshot details retain the runtime data. */
export function mergeSimulationResult(
  jobResult: SimulationJob["result"] | undefined,
  snapshotResult: SimulationJob["result"] | undefined,
): SimulationJob["result"] | undefined {
  if (!jobResult) return snapshotResult;
  if (!snapshotResult) return jobResult;
  return { ...snapshotResult, ...jobResult };
}

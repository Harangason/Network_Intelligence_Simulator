export const WIZARD_STEPS = ['engineering_model', 'routing', 'network_editor', 'parameters', 'capacity_timing',
  'validation', 'simulation', 'results_analysis', 'data_science_intelligence'] as const;
export const WIZARD_DONE = new Set(['COMPLETE', 'APPROVED', 'WARNING']);
export const WIZARD_PROGRESS_TIMEOUT_MS = 240_000;

type Workflow = {
  project_id?: string;
  statuses?: Record<string, string>;
  context?: { agent_execution?: { run_id?: string; request_revision?: string } };
};

export function completedFrontier(workflow: Workflow): number {
  let count = 0;
  for (const step of WIZARD_STEPS) {
    if (!WIZARD_DONE.has(workflow.statuses?.[step] ?? '')) break;
    count++;
  }
  return count;
}

function identity(workflow: Workflow): string | undefined {
  const execution = workflow.context?.agent_execution;
  if (!workflow.project_id || !execution?.run_id || !execution.request_revision) return undefined;
  return JSON.stringify([workflow.project_id, execution.run_id, execution.request_revision]);
}

/** One automatic continuation section between distinct, successfully applied reviews.
 * A real completed prefix can start the next 240-second section. Heartbeats,
 * retries, restarts and a previously completed prefix cannot extend it.
 * Playwright's independent 20-minute test deadline always remains in force.
 * Callers pass a monotonic clock; the clock is injectable for exact regressions.
 */
export class WizardProgressWatchdog {
  private deadline: number;
  private observedIdentity?: string;
  private frontier = 0;

  constructor(now: number, initialWorkflow?: Workflow) {
    this.deadline = now + WIZARD_PROGRESS_TIMEOUT_MS;
    if (initialWorkflow) {
      this.observedIdentity = identity(initialWorkflow);
      this.frontier = completedFrontier(initialWorkflow);
    }
  }

  remaining(now: number): number {
    const remaining = this.deadline - now;
    if (remaining <= 0) throw new Error(`Wizard made no new contiguous stage completion within ${WIZARD_PROGRESS_TIMEOUT_MS} ms (frontier ${this.frontier}/${WIZARD_STEPS.length}).`);
    return remaining;
  }

  observe(workflow: Workflow, now: number) {
    // Progress first observed after the deadline must not revive an expired run.
    this.remaining(now);
    const currentIdentity = identity(workflow);
    if (this.observedIdentity && currentIdentity !== this.observedIdentity) {
      throw new Error('Wizard project, run or request revision changed during an automatic continuation section.');
    }
    if (!currentIdentity) return { advanced: false, frontier: this.frontier, remainingMs: this.remaining(now) };
    if (!this.observedIdentity) {
      this.observedIdentity = currentIdentity;
      this.frontier = completedFrontier(workflow);
      return { advanced: false, frontier: this.frontier, remainingMs: this.remaining(now) };
    }
    const frontier = completedFrontier(workflow);
    const advanced = frontier > this.frontier;
    if (advanced) {
      this.frontier = frontier;
      this.deadline = now + WIZARD_PROGRESS_TIMEOUT_MS;
    }
    return { advanced, frontier: this.frontier, remainingMs: this.remaining(now) };
  }
}

export const WIZARD_STEPS = ['engineering_model', 'routing', 'network_editor', 'parameters', 'capacity_timing',
  'validation', 'simulation', 'results_analysis', 'data_science_intelligence'] as const;
export const WIZARD_DONE = new Set(['COMPLETE', 'APPROVED', 'WARNING']);
export const WIZARD_PROGRESS_TIMEOUT_MS = 240_000;

type Workflow = {
  project_id?: string;
  statuses?: Record<string, string>;
  context?: { agent_execution?: { run_id?: string; request_revision?: string } };
  parameters?: { preflight_warning_approval?: WarningApproval };
};
type WarningApproval = { snapshot_id?: string; signature?: string; actor?: string; approved_at?: string };
export type WarningReviewProof = {
  before: Workflow; after: Workflow; snapshotId: string; requestProject: string;
  submitted: { snapshot_id?: string; actor?: string }; status: number;
  response: { approval?: WarningApproval; preflight?: { warnings_allowed?: boolean; ready_for_simulation?: boolean } };
  started: number; startedWall: number; finishedWall: number;
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
  private warningApprovals = new Set<string>();

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

  commitWarningReview(proof: WarningReviewProof, now: number) {
    if (![now, proof.started, proof.startedWall, proof.finishedWall].every(Number.isFinite))
      throw new Error('Warning approval requires finite monotonic and wall clocks.');
    // The manual write must start in a live section and has its own 180s bound.
    // A legitimate acknowledged write can finish after the old automatic deadline.
    this.remaining(proof.started);
    const beforeIdentity = identity(proof.before), afterIdentity = identity(proof.after);
    const receipt = proof.response.approval, stored = proof.after.parameters?.preflight_warning_approval;
    const previous = proof.before.parameters?.preflight_warning_approval;
    if (!this.observedIdentity || beforeIdentity !== this.observedIdentity || afterIdentity !== beforeIdentity
      || proof.requestProject !== proof.before.project_id) throw new Error('Warning approval changed project, run or request revision.');
    if (now < proof.started || now - proof.started > 180_000 || proof.finishedWall < proof.startedWall)
      throw new Error('Warning approval exceeded its separate write boundary.');
    if (proof.status !== 200 || !proof.snapshotId || proof.submitted.snapshot_id !== proof.snapshotId
      || !proof.submitted.actor?.trim() || receipt?.actor !== proof.submitted.actor
      || receipt?.snapshot_id !== proof.snapshotId || !receipt?.signature?.trim()
      || proof.response.preflight?.warnings_allowed !== true || proof.response.preflight.ready_for_simulation !== true)
      throw new Error('Warning approval lacks a successful matching review receipt.');
    const approvedAt = Date.parse(receipt.approved_at ?? '');
    if (!Number.isFinite(approvedAt) || approvedAt < proof.startedWall || approvedAt > proof.finishedWall
      || !stored || ['snapshot_id', 'signature', 'actor', 'approved_at'].some(key => stored[key as keyof WarningApproval] !== receipt[key as keyof WarningApproval]))
      throw new Error('Warning approval is stale or not durably stored.');
    const key = JSON.stringify([beforeIdentity, receipt.signature]);
    if (this.warningApprovals.has(key) || previous?.signature === receipt.signature)
      throw new Error('Repeated or no-op warning approval cannot extend the section.');
    this.warningApprovals.add(key);
    this.frontier = Math.max(this.frontier, completedFrontier(proof.after));
    this.deadline = now + WIZARD_PROGRESS_TIMEOUT_MS;
    return { approvalIdentity: key, frontier: this.frontier, remainingMs: this.remaining(now) };
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

import type { IntelligenceSnapshot, OptimizationProposal } from "./workflow-api";

type IntelligenceLoaderOptions = {
  readProjectId(): string;
  getSnapshot(projectId: string): Promise<IntelligenceSnapshot>;
  assessSnapshot(projectId: string): Promise<IntelligenceSnapshot>;
  getProposals(projectId: string): Promise<{ items: OptimizationProposal[] }>;
  onProjectChange(): void;
  onSnapshot(snapshot: IntelligenceSnapshot): void;
  onProposals(proposals: OptimizationProposal[]): void;
  onLoading(loading: boolean): void;
  onError(error: unknown): void;
  onAssessed(): void;
};

export function createIntelligenceLoader(options: IntelligenceLoaderOptions) {
  let projectId: string | null = null;
  let generation = 0;
  let disposed = false;
  let active: {
    projectId: string;
    reassess: boolean;
    promise: Promise<void>;
    queuedAssessment?: Promise<void>;
  } | null = null;

  function refresh(reassess = false): Promise<void> {
    if (disposed) return Promise.resolve();
    const requestedProject = options.readProjectId();
    if (active?.projectId === requestedProject) {
      if (!reassess || active.reassess) return active.promise;
      active.queuedAssessment ??= active.promise.then(() => {
        if (!disposed && options.readProjectId() === requestedProject) return refresh(true);
      });
      return active.queuedAssessment;
    }

    const requestGeneration = ++generation;
    const isCurrent = () => !disposed && generation === requestGeneration
      && options.readProjectId() === requestedProject;
    if (projectId !== requestedProject) {
      projectId = requestedProject;
      options.onProjectChange();
    }
    options.onLoading(true);

    // Polling, focus and workflow events share one request for this project.
    const promise = Promise.resolve().then(async () => {
      try {
        if (!isCurrent()) return;
        let snapshot: IntelligenceSnapshot;
        let assessed = reassess;
        if (reassess) {
          snapshot = await options.assessSnapshot(requestedProject);
        } else {
          try {
            snapshot = await options.getSnapshot(requestedProject);
          } catch (error) {
            if (!isCurrent()) return;
            if (!(error instanceof Error && "status" in error && error.status === 404)) throw error;
            assessed = true;
            snapshot = await options.assessSnapshot(requestedProject);
          }
        }
        if (!isCurrent()) return;
        options.onSnapshot(snapshot);
        options.onError(null);
        if (assessed) options.onAssessed();

        // A proposal-list failure must not hide a successfully loaded assessment.
        const proposals = await options.getProposals(requestedProject);
        if (isCurrent()) options.onProposals(proposals.items);
      } catch (error) {
        if (isCurrent()) options.onError(error);
      } finally {
        if (generation === requestGeneration) active = null;
        if (isCurrent()) options.onLoading(false);
      }
    });
    active = { projectId: requestedProject, reassess, promise };
    return promise;
  }

  return {
    refresh,
    dispose() {
      disposed = true;
      ++generation;
      active = null;
    },
  };
}

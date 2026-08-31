const activeProjects = new Set<string>();

export async function runExclusiveProjectBuild<T>(projectId: string, build: () => Promise<T>): Promise<T> {
  if (activeProjects.has(projectId)) {
    throw new Error("Fuer dieses Projekt arbeitet bereits ein Agent. Der bestehende Lauf wird fortgesetzt.");
  }
  activeProjects.add(projectId);
  try {
    return await build();
  } finally {
    activeProjects.delete(projectId);
  }
}

// A draft is editable input, never a confirmed wizard request or write authority.
export function projectIntakeKey(projectId: string) {
  return `networkis:project-intake:v1:${projectId}`;
}

export function parseProjectIntake(raw: string | null, projectId: string): string | null {
  try {
    const value = JSON.parse(raw ?? 'null');
    return value?.projectId === projectId && typeof value.requirement === 'string'
      && value.requirement.trim().length > 0 && value.requirement.length <= 16000
      ? value.requirement : null;
  } catch { return null; }
}

/** Select existing preflight evidence for its source; never recalculate findings. */
export type SourceFinding = {
  severity: string; code: string; message: string; blocking?: boolean;
  object_type?: string; object_id?: string; category?: string; step?: string;
};

const categoryStage: Record<string, string> = {
  engineering_model: 'engineering_model', routing: 'routing', network: 'network_editor',
  physical: 'network_editor', technology: 'parameters', parameters: 'parameters',
  capacity: 'capacity_timing', timing: 'capacity_timing', reliability: 'capacity_timing',
  synchronization: 'capacity_timing', addressing: 'engineering_model',
};

export function findingsAtSource(findings: SourceFinding[], scope: {
  projectId: string; snapshotProjectId?: string; stage?: string; objectType?: string; objectId?: string;
}): SourceFinding[] {
  if (!scope.projectId || scope.snapshotProjectId !== scope.projectId) return [];
  return findings.filter(finding => {
    if (!finding.blocking && !['ERROR', 'BLOCKER', 'CRITICAL'].includes(finding.severity.toUpperCase())) return false;
    if (scope.objectId) return finding.object_id === scope.objectId && finding.object_type === scope.objectType;
    if (!scope.stage) return false;
    if (finding.object_id && !(finding.object_type === 'WorkflowParameters' && finding.object_id === scope.projectId)) return false;
    return (finding.step || categoryStage[finding.category || '']) === scope.stage;
  });
}

export function parameterIsUnverified(parameters: Record<string, unknown>, key: string, displayedTechnology?: string): boolean {
  if (displayedTechnology && parameters.technology !== displayedTechnology) return true;
  const value = parameters[key];
  return value === undefined || value === null || (typeof value === 'string' && !value.trim());
}

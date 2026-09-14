import type { WorkflowState } from './workflow-api.ts';

export async function requestWizardCancellation(projectId: string, runId: string, {
  confirm = (message: string) => window.confirm(message),
  request = fetch,
  onConfirmed = () => {},
  requestRevision,
}: { confirm?: (message: string) => boolean; request?: typeof fetch; onConfirmed?: () => void; requestRevision?: string } = {}): Promise<WorkflowState | null> {
  if (!confirm('Auftrag wirklich abbrechen? Bereits übernommene Modelldaten bleiben erhalten.')) return null;
  onConfirmed();
  const response = await request(`/api/engineering/agent/runs/${encodeURIComponent(runId)}/cancel`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Project-ID': projectId },
    body: JSON.stringify({ confirmed: true, ...(requestRevision ? { request_revision: requestRevision } : {}) }), signal: AbortSignal.timeout(12000),
  });
  const result = await response.json();
  if (!response.ok || !result.success) throw new Error(result.error ?? result.findings?.[0]?.message ?? 'Abbruch nicht bestätigt. Bitte erneut versuchen.');
  return result.data;
}

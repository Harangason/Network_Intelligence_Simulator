"use client";

import { useState } from 'react';
import { readActiveProjectId, withProjectParam } from '@/lib/user-settings';

type Action = Record<string, unknown>;
const paths = new Set(['/studio', '/studio/engineering', '/studio/routing', '/studio/capacity',
  '/studio/validation', '/studio/simulation', '/studio/results', '/studio/trace-analysis', '/studio/intelligence']);

export function AssistantCapabilityCards({ actions, projectId }: { actions: Action[]; projectId: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const cards = actions.filter(item => item.type === 'CAPABILITY' && typeof item.capability_id === 'string');
  if (!cards.length) return null;
  async function open(action: Action) {
    if (busy) return;
    setBusy(true); setError('');
    try {
      if (readActiveProjectId() !== projectId || action.project_id !== projectId)
        throw new Error('Das Projekt wurde gewechselt. Bitte die Fähigkeiten im aktuellen Projekt neu aufrufen.');
      // Resolve an allowlisted capability again; chat/model text cannot supply a URL or a write.
      const response = await fetch(`/api/engineering/agent/capabilities?id=${encodeURIComponent(String(action.capability_id))}`, {
        headers: { 'X-Project-ID': projectId }, cache: 'no-store',
      });
      const result = await response.json();
      const item = result.data?.capabilities?.[0];
      if (!response.ok || !result.success || !item?.available || !paths.has(item.path))
        throw new Error('Dieser Ablauf ist momentan nicht verfügbar.');
      if (readActiveProjectId() !== projectId || result.data.project_id !== projectId)
        throw new Error('Das Projekt wurde während der Anfrage gewechselt.');
      const query = new URLSearchParams();
      if (item.resource) query.set('resource', item.resource);
      if (item.launch === 'create') query.set('create', '1');
      else if (item.launch) query.set('assistant', item.launch);
      if (item.id === 'repair' && typeof action.repair_workload === 'string' && /^repair-[a-f0-9]{32}$/.test(action.repair_workload)) query.set('repair_workload', action.repair_workload);
      if (item.id === 'parameters') query.set('mode', 'parameter');
      if (item.id === 'spatial') query.set('mode', 'network');
      window.location.assign(withProjectParam(`${item.path}?${query}`, projectId));
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Ablauf konnte nicht geöffnet werden.'); }
    finally { setBusy(false); }
  }
  return <><div className="assistant-capability-cards" aria-label="Fähigkeiten">
    {cards.map(action => <button type="button" key={String(action.capability_id)} disabled={busy}
      onClick={() => void open(action)}><strong>{String(action.label)}</strong><span>{String(action.description ?? '')}</span></button>)}
  </div>{error && <p role="alert">{error}</p>}</>;
}

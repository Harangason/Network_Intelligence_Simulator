"use client";

import { useState } from 'react';
import { readActiveProjectId, withProjectParam } from '@/lib/user-settings';
import { projectIntakeKey } from '@/lib/agent/project-intake';

type Action = Record<string, unknown>;
const paths = new Set(['/studio', '/studio/engineering', '/studio/routing', '/studio/capacity',
  '/studio/validation', '/studio/simulation', '/studio/results', '/studio/trace-analysis', '/studio/intelligence']);

export function AssistantCapabilityCards({ actions, projectId, onStart }: { actions: Action[]; projectId: string; onStart?: (prompt: string) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const cards = actions.filter(item => item.type === 'CAPABILITY' && typeof item.capability_id === 'string');
  if (!cards.length) return null;
  async function open(action: Action, runInChat = false) {
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
      if (runInChat && onStart) {
        const execution = item.execution && typeof item.execution === 'object'
          ? item.execution as Record<string, unknown> : {};
        const executionMode = String(execution.mode ?? 'ANALYSIS_ONLY');
        const prompt = `Führe „${item.label}“ agentisch im aktuellen Projekt aus. Ziel: ${item.description}\n` +
          `Arbeitsmodus: ${executionMode}. Das ist ein Ausführungsauftrag, keine Bitte um Navigation: Gib keine Fähigkeitskachel oder Seitenverknüpfung zurück. ` +
          `Prüfe zuerst den aktuellen Modellstand, nutze die passenden Engineering-Werkzeuge und zeige Befunde, Rückfragen sowie validierte Ergebnisse hier im Chat. ` +
          `Bei Änderungen erstelle einen prüfbaren Vorschlag und warte auf meine Freigabe; behaupte keine Übernahme vorher.`;
        onStart(prompt);
        return;
      }
      const query = new URLSearchParams();
      if (item.resource) query.set('resource', item.resource);
      if (item.launch === 'create') query.set('create', '1');
      else if (item.launch) query.set('assistant', item.launch);
      if (item.id === 'repair' && typeof action.repair_workload === 'string' && /^repair-[a-f0-9]{32}$/.test(action.repair_workload)) query.set('repair_workload', action.repair_workload);
      if (item.id === 'parameters') query.set('mode', 'parameter');
      if (item.id === 'spatial') query.set('mode', 'network');
      if (item.id === 'project' && typeof action.draft_id === 'string') {
        const draftResponse = await fetch('/api/engineering/agent/project-draft', {
          headers: { 'X-Project-ID': projectId }, cache: 'no-store',
        });
        const current = await draftResponse.json();
        if (!draftResponse.ok || !current.success || current.data?.draft_id !== action.draft_id)
          throw new Error('Dieser Projektentwurf ist nicht mehr aktuell. Bitte den aktuellen Entwurf öffnen.');
        if (readActiveProjectId() !== projectId) throw new Error('Das Projekt wurde inzwischen gewechselt.');
        query.set('draft', action.draft_id);
      }
      if (item.id === 'project' && !action.draft_id && typeof action.requirement === 'string' && action.requirement.trim()) {
        if (action.requirement.length > 16000) throw new Error('Die Projektanforderung ist zu lang.');
        window.sessionStorage.setItem(projectIntakeKey(projectId), JSON.stringify({
          projectId, requirement: action.requirement,
        }));
      }
      window.location.assign(withProjectParam(`${item.path}?${query}`, projectId));
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Ablauf konnte nicht geöffnet werden.'); }
    finally { setBusy(false); }
  }
  return <><div className="assistant-capability-cards" aria-label="Fähigkeiten">
    {cards.map(action => <article key={String(action.capability_id)}>
      <strong>{String(action.label)}</strong><span>{String(action.description ?? '')}</span>
      {onStart && <button type="button" disabled={busy} onClick={() => void open(action, true)}>Im Chat starten</button>}
      <button type="button" className="secondary" disabled={busy} onClick={() => void open(action)}>Arbeitsbereich öffnen</button>
    </article>)}
  </div>{error && <p role="alert">{error}</p>}</>;
}

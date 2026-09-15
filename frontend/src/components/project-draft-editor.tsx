"use client";

import { useEffect, useRef, useState } from 'react';
import { readActiveProjectId, readUserSettings, writeUserSettings, withProjectParam } from '@/lib/user-settings';
import type { EngineeringProposal } from '@/lib/agent/engineering-agent';
import styles from './project-draft-editor.module.css';

type Device = { id: string; name: string; role: string; technology: string | null; owner_id: string | null; command?: Record<string, unknown> | null; purpose?: string | null; known_kind?: boolean };
type Draft = { source_format?: string; draft_id: string; revision: number; original_requirement: string; sources?: { text: string }[]; industry: string | null; allow_simulation_defaults?: boolean; model_proposal_id?: string; devices: Device[]; issues: { id: string; message: string }[] };
const openCloseCommand = { length_bits: 1, data_type: 'boolean', factor: 1, unit: 'code', min_value: 0, max_value: 1,
  semantic: { semantic_type: 'BOOLEAN' }, data: { enum_values: { CLOSE: 0, OPEN: 1 } } };
function commandChoice(command: Device['command']) {
  if (!command) return '';
  const values = (command.data as { enum_values?: Record<string, unknown> } | undefined)?.enum_values;
  return command.length_bits === 1 && values?.CLOSE === 0 && values?.OPEN === 1 && Object.keys(values).length === 2 ? 'OPEN_CLOSE' : 'CUSTOM';
}
const operationId = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join('');

export type ProjectDraftStatus = { draftId: string; revision: number; ready: boolean };
export function ProjectDraftEditor({ projectId, draftId, onProposal, onStateChange }: { projectId: string; draftId: string; onProposal?: (proposal: EngineeringProposal) => void; onStateChange?: (status: ProjectDraftStatus) => void }) {
  const [draft, setDraft] = useState<Draft | null>(null);
  const [addition, setAddition] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState('');
  const [dirty, setDirty] = useState(false);
  const [removedDeviceIds, setRemovedDeviceIds] = useState<string[]>([]);
  const [conflictDraft, setConflictDraft] = useState<Draft | null>(null);
  const [retainedInput, setRetainedInput] = useState('');
  const [projectName, setProjectName] = useState('');
  const epoch = useRef(0);
  const pending = useRef<{ signature: string; operation: string } | null>(null);
  const url = '/api/engineering/agent/project-draft';
  const structured = draft?.source_format === 'WIZARD_V2';
  const ready = !!draft && !busy && !dirty && !addition.trim() && !draft.issues.length && (structured || !!draft.allow_simulation_defaults);
  useEffect(() => {
    onStateChange?.({ draftId, revision: draft?.revision ?? 0, ready });
  }, [draftId, draft?.revision, ready, onStateChange]);
  useEffect(() => {
    const controller = new AbortController();
    epoch.current += 1; pending.current = null;
    setDraft(null); setError(''); setAddition(''); setSaved(''); setBusy(false); setDirty(false);
    setRemovedDeviceIds([]);
    setConflictDraft(null); setRetainedInput('');
    void fetch(url, { headers: { 'X-Project-ID': projectId }, cache: 'no-store', signal: controller.signal })
      .then(async response => {
        const result = await response.json();
        if (!response.ok || !result.success || result.data?.draft_id !== draftId) throw new Error('Dieser Entwurf ist nicht mehr aktuell.');
        if (!controller.signal.aborted) setDraft(result.data);
        if (result.data.model_proposal_id && onProposal) {
          const proposalResponse = await fetch(`/api/engineering/agent/proposals/${encodeURIComponent(result.data.model_proposal_id)}`, {
            headers: { 'X-Project-ID': projectId }, cache: 'no-store', signal: controller.signal,
          });
          const proposalResult = await proposalResponse.json();
          if (proposalResponse.ok && proposalResult.success && !controller.signal.aborted) onProposal(proposalResult.data);
        }
      }).catch(cause => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Entwurf konnte nicht geladen werden.'); });
    return () => { controller.abort(); epoch.current += 1; };
  }, [projectId, draftId, onProposal]);
  async function save(action: 'AMEND' | 'RESOLVE') {
    if (!draft || busy || (action === 'AMEND' && dirty)) return;
    const requestEpoch = epoch.current;
    setBusy(true); setError(''); setSaved('');
    try {
      if (readActiveProjectId() !== projectId) throw new Error('Das aktive Projekt wurde gewechselt.');
      const data = { action, revision: draft.revision,
        ...(action === 'AMEND' ? { requirement: addition } : {
          industry: draft.industry, allow_simulation_defaults: draft.allow_simulation_defaults,
          remove_device_ids: removedDeviceIds,
          devices: draft.devices.map(device => ({ device_id: device.id,
            name: device.name, owner_id: device.owner_id, technology: device.technology, command: device.command, purpose: device.purpose || null })),
        }),
      };
      const signature = JSON.stringify(data);
      if (pending.current?.signature !== signature) pending.current = { signature, operation: operationId() };
      const sessionResponse = await fetch('/api/engineering/agent/review-session', { cache: 'no-store' });
      if (!sessionResponse.ok) throw new Error('Bearbeitungssitzung konnte nicht geöffnet werden.');
      const session = await sessionResponse.json();
      if (epoch.current !== requestEpoch || readActiveProjectId() !== projectId) return;
      const response = await fetch(url, { method: 'POST', headers: {
        'Content-Type': 'application/json', 'X-Project-ID': projectId,
        'X-Human-Review': 'confirmed', 'X-Review-CSRF': session.csrf_token,
      }, body: JSON.stringify({ ...data, operation_id: pending.current.operation }) });
      const result = await response.json();
      if (epoch.current !== requestEpoch || readActiveProjectId() !== projectId) return;
      if (result.status === 'CONFLICT') {
        const latestResponse = await fetch(url, { headers: { 'X-Project-ID': projectId }, cache: 'no-store' });
        const latest = await latestResponse.json();
        if (epoch.current !== requestEpoch || readActiveProjectId() !== projectId) return;
        if (latestResponse.ok && latest.success && latest.data?.draft_id === draftId) setConflictDraft(latest.data);
      }
      if (!response.ok || !result.success) throw new Error(result.findings?.[0]?.message ?? 'Änderung nicht gespeichert. Deine Eingabe bleibt erhalten.');
      if (result.data.draft.draft_id !== draftId || !result.data.receipt?.accepted) throw new Error('Die Speicherung wurde nicht bestätigt.');
      pending.current = null;
      setDraft(result.data.draft); setAddition(''); setDirty(false); setSaved(`Revision ${result.data.draft.revision} gespeichert.`);
      setRemovedDeviceIds([]);
      setConflictDraft(null);
    } catch (cause) { if (epoch.current === requestEpoch) setError(cause instanceof Error ? cause.message : 'Speichern fehlgeschlagen.'); }
    finally { if (epoch.current === requestEpoch) setBusy(false); }
  }
  const owners = draft?.devices.filter(device => ['CONTROLLER', 'GATEWAY'].includes(device.role)) ?? [];
  async function plan() {
    if (!draft || busy || dirty) return;
    const requestEpoch = epoch.current;
    setBusy(true); setError('');
    try {
      if (readActiveProjectId() !== projectId) throw new Error('Das aktive Projekt wurde gewechselt.');
      const session = await fetch('/api/engineering/agent/review-session', { cache: 'no-store' }).then(response => response.json());
      if (epoch.current !== requestEpoch || readActiveProjectId() !== projectId) return;
      const response = await fetch(url + '/plan', { method: 'POST', headers: { 'Content-Type': 'application/json',
        'X-Project-ID': projectId, 'X-Human-Review': 'confirmed', 'X-Review-CSRF': session.csrf_token },
        body: JSON.stringify({ draft_id: draft.draft_id, revision: draft.revision }) });
      const result = await response.json();
      if (epoch.current !== requestEpoch || readActiveProjectId() !== projectId) return;
      if (!response.ok || !result.success || !result.data.proposal_id) throw new Error(result.findings?.[0]?.message ?? 'Modellvorschlag konnte nicht erstellt werden.');
      onProposal?.(result.data);
    } catch (cause) { if (epoch.current === requestEpoch) setError(cause instanceof Error ? cause.message : 'Planung fehlgeschlagen.'); }
    finally { if (epoch.current === requestEpoch) setBusy(false); }
  }
  async function createProject() {
    if (!draft || busy || dirty || !projectName.trim()) return;
    const requestEpoch = epoch.current;
    setBusy(true); setError('');
    try {
      if (readActiveProjectId() !== projectId) throw new Error('Das aktive Projekt wurde gewechselt.');
      const data = { draft_id: draft.draft_id, revision: draft.revision, name: projectName.trim() };
      const signature = JSON.stringify({ createProject: data });
      if (pending.current?.signature !== signature) pending.current = { signature, operation: operationId() };
      const operation = pending.current.operation;
      const session = await fetch('/api/engineering/agent/review-session', { cache: 'no-store' }).then(response => response.json());
      if (epoch.current !== requestEpoch || readActiveProjectId() !== projectId) return;
      const response = await fetch(url + '/create-project', { method: 'POST', headers: { 'Content-Type': 'application/json',
        'X-Project-ID': projectId, 'X-Human-Review': 'confirmed', 'X-Review-CSRF': session.csrf_token },
        body: JSON.stringify({ ...data, operation_id: operation }) });
      const result = await response.json();
      if (epoch.current !== requestEpoch || readActiveProjectId() !== projectId) return;
      if (!response.ok || !result.success || !result.data.receipt?.accepted) throw new Error(result.findings?.[0]?.message ?? 'Projektanlage nicht bestätigt.');
      const target = result.data.project_id;
      if (typeof target !== 'string' || !target.startsWith('network-project-') || !result.data.draft?.draft_id) throw new Error('Ungültige Projektantwort.');
      writeUserSettings({ ...readUserSettings(), activeProject: target });
      window.location.assign(withProjectParam(`/studio/agent?draft=${encodeURIComponent(result.data.draft.draft_id)}`, target));
    } catch (cause) { if (epoch.current === requestEpoch) setError(cause instanceof Error ? cause.message : 'Projektanlage fehlgeschlagen.'); }
    finally { if (epoch.current === requestEpoch) setBusy(false); }
  }
  function edit(id: string, field: keyof Device, value: string | null | Record<string, unknown>) {
    setSaved(''); setDirty(true);
    setDraft(current => current && ({ ...current, devices: current.devices.map(device => device.id === id ? { ...device, [field]: value } : device) }));
  }
  return <section className={styles.editor} aria-label="Gespeicherter Projektentwurf">
    <h4>Projektentwurf bearbeiten</h4>
    {error && <p role="alert">{error}</p>}
    {conflictDraft && <section aria-label="Entwurfskonflikt">
      <p>Inzwischen ist Revision {conflictDraft.revision} gespeichert. Deine Eingaben stehen weiterhin im Formular.</p>
      <button type="button" className="button secondary" disabled={busy} onClick={() => {
        setRetainedInput(JSON.stringify({ devices: draft?.devices, industry: draft?.industry,
          allow_simulation_defaults: draft?.allow_simulation_defaults, remove_device_ids: removedDeviceIds,
          addition }, null, 2));
        setDraft(conflictDraft); setConflictDraft(null); setDirty(false); setRemovedDeviceIds([]);
        setError(''); setSaved('Aktuellen Stand geladen. Deine bisherigen Eingaben bleiben unten als Kopie erhalten.');
        pending.current = null;
      }}>Aktuellen Stand laden und Eingabekopie behalten</button>
    </section>}
    {retainedInput && <label>Erhaltene Eingaben vor dem Konflikt<textarea readOnly rows={8} value={retainedInput} /></label>}
    {draft && <>
      <p>Revision {draft.revision} · {draft.devices.length} Geräte</p>
      <label>Projektbeschreibung<textarea readOnly rows={4} value={draft.sources?.map(source => source.text).join('\n\n') || draft.original_requirement} /></label>
      <p>Die bestätigte Beschreibung bleibt nachvollziehbar. Ergänzungen und Korrekturen kannst du unten speichern.</p>
      {structured && <p>Dieser Entwurf enthält die vollständigen bestätigten Wizardangaben einschließlich Anschlüssen, Systemgraph und HMI-Auswahl. Ergänzungen werden auf diesen Angaben aufgebaut und erneut geprüft.</p>}
      {!structured && <>
      <label>Einsatzbereich<input disabled={busy} value={draft.industry ?? ''} onChange={event => { setDirty(true); setDraft({ ...draft, industry: event.target.value }); }} /></label>
      <div className={styles.devices}>{draft.devices.map(device => <fieldset key={device.id} disabled={busy}>
        <legend>{device.name} · {device.role}</legend>
        <button type="button" className="button secondary" onClick={() => {
          setRemovedDeviceIds(current => [...current, device.id]); setDirty(true); setSaved('');
          setDraft(current => current && ({ ...current, devices: current.devices.filter(item => item.id !== device.id)
            .map(item => item.owner_id === device.id ? { ...item, owner_id: null } : item) }));
        }}>Aus Entwurf entfernen</button>
        <label>Name<input value={device.name} onChange={event => edit(device.id, 'name', event.target.value)} /></label>
        <label>Messgröße oder Geräteaufgabe<input value={device.purpose ?? ''} placeholder="Zum Beispiel: Temperatur messen" onChange={event => edit(device.id, 'purpose', event.target.value || null)} /></label>
        {['SENSOR', 'ACTUATOR'].includes(device.role) && <label>Verarbeitender Controller<select value={device.owner_id ?? ''} onChange={event => edit(device.id, 'owner_id', event.target.value || null)}>
          <option value="">Noch offen</option>{owners.map(owner => <option key={owner.id} value={owner.id}>{owner.name}</option>)}
        </select></label>}
        <label>Anschlusstechnologie<input placeholder="Noch offen" value={device.technology ?? ''} onChange={event => edit(device.id, 'technology', event.target.value || null)} /></label>
        {device.role === 'ACTUATOR' && <label>Ventilbefehl<select value={commandChoice(device.command)} onChange={event => { if (event.target.value !== 'CUSTOM') edit(device.id, 'command', event.target.value ? openCloseCommand : null); }}>
          <option value="">Noch offen</option><option value="OPEN_CLOSE">Auf / Zu · 1 Bit: 0 = Zu, 1 = Auf</option>
          {commandChoice(device.command) === 'CUSTOM' && <option value="CUSTOM">Vorhandene individuelle Kodierung beibehalten</option>}
        </select></label>}
      </fieldset>)}</div>
      <label><span>Technische Parameter</span><select disabled={busy} value={draft.allow_simulation_defaults ? 'defaults' : ''}
        onChange={event => { setDirty(true); setDraft({ ...draft, allow_simulation_defaults: event.target.value === 'defaults' }); }}>
        <option value="">Noch festzulegen</option><option value="defaults">Technologie-Defaults für die Simulation verwenden</option>
      </select></label>
      <button type="button" className="button secondary" disabled={busy} onClick={() => void save('RESOLVE')}>Angaben speichern</button>
      </>}
      <label>Anforderung ergänzen<textarea disabled={busy} placeholder={'Zum Beispiel: Controller namens "Regelung" und zwei Ventile.'} value={addition} onChange={event => setAddition(event.target.value)} /></label>
      {dirty && <p>Speichere zuerst die geänderten Geräteangaben, bevor du die Anforderung ergänzt.</p>}
      <button type="button" className="button secondary" disabled={busy || dirty || !addition.trim()} onClick={() => void save('AMEND')}>Ergänzung speichern</button>
      <details><summary>Offene Angaben ({draft.issues.length})</summary><ul>{draft.issues.map(issue => <li key={issue.id}>{issue.message}</li>)}</ul></details>
      {onProposal && <button type="button" className="button primary" disabled={busy || dirty || !!addition.trim()} onClick={() => void plan()}>Modellvorschlag erstellen</button>}
      <details><summary>Als neues Projekt verwenden</summary>
        <label>Neuer Projektname<input disabled={busy} value={projectName} maxLength={120} onChange={event => setProjectName(event.target.value)} /></label>
        <button type="button" className="button secondary" disabled={busy || dirty || !!addition.trim() || !projectName.trim()} onClick={() => void createProject()}>Neues Projekt anlegen und öffnen</button>
      </details>
      {saved && <p role="status">{saved}</p>}
    </>}
  </section>;
}

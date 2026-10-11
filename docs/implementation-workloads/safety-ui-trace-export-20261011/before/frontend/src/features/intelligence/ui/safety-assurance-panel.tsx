'use client';

import {useCallback, useEffect, useRef, useState} from 'react';
import {readActiveProjectId} from '@/features/settings/lib/user-settings';
import {useWorkflowRefresh} from '@/features/workflow/lib/use-workflow-refresh';
import {notifyWorkflowChanged} from '@/features/workflow/ui/workflow-header';

type Requirement = {id: string; name: string; version: number; function_id: string; configuration: Record<string, unknown>};
type AssessmentRow = {id: string; name: string; revision: number; technical_status: string; gaps: string[]; checks: Array<{id: string; kind: string; status: string; sample_count: number; deadline_ms?: number; freshness_ms?: number; observed_max_latency_ms?: number; observed_max_data_age_ms?: number; ftti_ms?: number; observations?: Array<{detection_ms: number; reaction_ms: number; observed_state: string; status: string}>}>; evidence_event_ids: string[]};
type SafetyData = {project_id: string; requirements: Requirement[]; functions: Array<{id: string; name: string}>; routes: Array<{id: string; name?: string}>;
  profiles: Array<{standard: string; url: string}>; bundle: {sha256: string; payload: {snapshot_id: string; freshness: string; execution_status: string;
    assessment: {technical_status: string; requirements: AssessmentRow[]; limitations: string[]}}}};

const template = {profile: {standard: 'ISO 26262', edition: '2018', domain: 'road_vehicle', applicability: 'UNRESOLVED', reason: 'Fachliche Anwendbarkeit festlegen', clause_refs: [], work_product_refs: []},
  hazard_ref: '', safety_goal_ref: '', route_ids: [], criteria: {required_protections: [], fault_cases: []}};

export function SafetyAssurancePanel() {
  const [data, setData] = useState<SafetyData | null>(null), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<Requirement | null>(null), [name, setName] = useState(''), [owner, setOwner] = useState('');
  const [text, setText] = useState(JSON.stringify(template, null, 2)), [open, setOpen] = useState(false);
  const generation = useRef(0);
  const loadedProject = useRef<string | null>(null);
  const load = useCallback(async () => {
    const ticket = ++generation.current, project = readActiveProjectId();
    if (loadedProject.current !== project) {loadedProject.current = project; setData(null); setOpen(false); setEditing(null);}
    try {
      const response = await fetch('/api/engineering/intelligence/safety', {headers: {'X-Project-ID': project}, cache: 'no-store'});
      const next = await response.json();
      if (!response.ok) throw new Error(next.error || 'Safety-Daten nicht verfügbar.');
      if (ticket === generation.current && project === readActiveProjectId()) {setData(next); setError('');}
    } catch (cause) {if (ticket === generation.current) setError(cause instanceof Error ? cause.message : 'Safety-Daten nicht verfügbar.');}
  }, []);
  useEffect(() => {void load(); return () => {++generation.current;};}, [load]);
  useWorkflowRefresh(load);
  function edit(row: Requirement | null) {
    setEditing(row); setName(row?.name ?? ''); setOwner(row?.function_id ?? '');
    setText(JSON.stringify(row?.configuration ?? template, null, 2)); setOpen(true);
  }
  async function save() {
    const project = readActiveProjectId(); setBusy(true); setError('');
    try {
      const configuration = JSON.parse(text);
      const response = await fetch(`/api/engineering/safety-requirements${editing ? '/' + encodeURIComponent(editing.id) : ''}`, {
        method: editing ? 'PATCH' : 'POST', headers: {'Content-Type': 'application/json', 'X-Project-ID': project},
        body: JSON.stringify({name, function_id: owner, configuration, ...(editing ? {expected_version: editing.version} : {})})});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Anforderung konnte nicht gespeichert werden.');
      if (project === readActiveProjectId()) {setOpen(false); await load(); notifyWorkflowChanged();}
    } catch (cause) {setError(cause instanceof Error ? cause.message : 'Ungültige Anforderung.');} finally {setBusy(false);}
  }
  const payload = data?.bundle.payload;
  return <section className="panel safety-assurance-panel" aria-labelledby="safety-assurance-title">
    <header className="intelligence-toolbar"><div><p className="eyebrow">Safety & Regulatory Assurance</p><h2 id="safety-assurance-title">Sicherheitsanforderungen und Prüfbelege</h2></div>
      <div className="analysis-actions"><button className="button secondary" type="button" disabled={busy} onClick={() => edit(null)}>Anforderung erfassen</button>
        {data && <a className="button secondary" href={`/api/engineering/intelligence/safety?project=${encodeURIComponent(data.project_id)}&download=1`} download>Belege für EIP exportieren</a>}</div></header>
    <p>ISO 26262, UN R155 und UN R156 erhalten eigene Anwendbarkeit, Ausgabe und Nachweiskette. Technische Ergebnisse erteilen keine Norm-, ASIL- oder Typgenehmigungsfreigabe.</p>
    {error && <p role="alert">{error} <button type="button" onClick={() => void load()}>Neu laden</button></p>}
    <dl className="intelligence-counts"><div><dt>Technische Prüfung</dt><dd>{payload?.freshness === 'CURRENT' ? payload.assessment.technical_status : 'NOT_EVALUATED'}</dd></div>
      <div><dt>Belegstand</dt><dd>{payload?.freshness ?? 'Nicht geladen'}</dd></div><div><dt>Normative Vollständigkeit</dt><dd>NOT_EVALUATED</dd></div><div><dt>Fachliche Freigabe</dt><dd>Unabhängiges Review in EIP erforderlich</dd></div></dl>
    {data && !data.requirements.length && <p>Keine Sicherheitsanforderungen erfasst. Fristen, ASIL und FTTI werden nicht automatisch zugewiesen.</p>}
    <div className="table-scroll"><table><thead><tr><th>Anforderung</th><th>Funktion</th><th>Norm / Ausgabe</th><th>Anwendbarkeit</th><th>Revision</th><th>Aktion</th></tr></thead>
      <tbody>{data?.requirements.map(row => {const profile = row.configuration.profile as {standard: string; edition: string; applicability: string}; return <tr key={row.id}>
        <td>{row.name}</td><td>{data.functions.find(item => item.id === row.function_id)?.name ?? 'Verknüpfung fehlt'}</td><td>{profile.standard} · {profile.edition}</td><td>{profile.applicability}</td><td>{row.version}</td><td><button type="button" className="button secondary tiny" onClick={() => edit(row)}>Bearbeiten</button></td></tr>;})}</tbody></table></div>
    {payload?.assessment.requirements.map(row => <details key={row.id}><summary>{row.name} · eingefrorene Revision {row.revision} · {row.technical_status}{payload.freshness !== 'CURRENT' ? ' · historisch' : ''}</summary>
      <table><thead><tr><th>Prüfung</th><th>Art</th><th>Ergebnis</th><th>Stichproben</th><th>Messwerte / Grenzen</th></tr></thead><tbody>{row.checks.map(check => <tr key={check.kind + check.id}><td>{check.id}</td><td>{check.kind}</td><td>{check.status}</td><td>{check.sample_count}</td><td>{check.kind === 'COMMUNICATION'
        ? <>E2E: {check.observed_max_latency_ms ?? '—'} / {check.deadline_ms ?? '—'} ms · Alter: {check.observed_max_data_age_ms ?? '—'} / {check.freshness_ms ?? '—'} ms</>
        : <>FTTI: {check.ftti_ms ?? '—'} ms{check.observations?.map((observation, index) => <p key={index}>Erkennung {observation.detection_ms} ms · Reaktion {observation.reaction_ms} ms · {observation.observed_state} · {observation.status}</p>)}</>}</td></tr>)}</tbody></table>
      <ul>{row.gaps.map(gap => <li key={gap}>{gap}</li>)}</ul><details><summary>Originale Ereignisbelege</summary><p>{row.evidence_event_ids.join(', ') || 'Keine korrelierten Belege'}</p></details></details>)}
    <details><summary>Normquellen und Bewertungsumfang</summary><ul>{data?.profiles.map(profile => <li key={profile.standard}><a href={profile.url} target="_blank" rel="noopener noreferrer">{profile.standard}</a></li>)}</ul>
      <p>Das Quellenverzeichnis führt die Normreferenzen mit getrennten Rechtehinweisen. Ausgabe und Änderungsserie müssen für jedes Projekt fachlich bestätigt werden.</p></details>
    {open && <details open><summary>Anforderung {editing ? 'bearbeiten' : 'erfassen'}</summary><form onSubmit={event => {event.preventDefault(); void save();}}>
      <fieldset disabled={busy}><label>Name<input value={name} onChange={event => setName(event.target.value)} required maxLength={300} /></label>
        <label>Funktion<select required value={owner} onChange={event => setOwner(event.target.value)}><option value="">Bitte auswählen</option>{data?.functions.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
        <p>Die Konfiguration verbindet Gefährdung, Sicherheitsziel, Normprofil, Routen und explizite Prüfgrenzen. EIP-Quellenrevisionen können unter „eip“ hinterlegt werden. Fehlende Nachweise bleiben offen.</p>
        <label>Versionierte Konfiguration<textarea rows={18} value={text} onChange={event => setText(event.target.value)} required spellCheck={false} style={{width: '100%', fontFamily: 'monospace'}} /></label>
        <details><summary>Verfügbare Routenreferenzen</summary><ul>{data?.routes.map(row => <li key={row.id}>{row.name ?? row.id} <code>{row.id}</code></li>)}</ul></details>
        <button className="button primary" type="submit">{busy ? 'Speichern …' : 'Anforderung speichern'}</button> <button className="button secondary" type="button" onClick={() => setOpen(false)}>Schließen</button></fieldset>
    </form></details>}
  </section>;
}

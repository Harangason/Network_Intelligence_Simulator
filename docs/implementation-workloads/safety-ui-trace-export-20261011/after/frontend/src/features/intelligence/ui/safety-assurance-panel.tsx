'use client';

import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {readActiveProjectId} from '@/features/settings/lib/user-settings';
import {useWorkflowRefresh} from '@/features/workflow/lib/use-workflow-refresh';
import {notifyWorkflowChanged} from '@/features/workflow/ui/workflow-header';
import styles from './safety-assurance-panel.module.css';

type FaultCase = {id: string; type: string; ftti_ms: number | ''; detection_ms: number | ''; safe_state: string; receiver_id: string};
type Configuration = {
  profile: {standard: string; edition: string; domain: string; applicability: string; reason: string; clause_refs?: string[]; work_product_refs?: string[]};
  hazard_ref: string; safety_goal_ref: string; route_ids: string[];
  integrity?: {model: string; level: string; decision_ref: string};
  criteria: {deadline_ms?: number; freshness_ms?: number; required_protections?: string[]; fault_cases?: FaultCase[]};
  eip?: {project_id: string; requirement_ref: string; source_revisions: Record<string, number>};
};
type Requirement = {id: string; name: string; version: number; function_id: string; configuration: Configuration};
type Membership = {cluster_id?: string; cluster_name?: string; system_owner_id?: string; systemOwnerId?: string};
type Hardware = {id: string; name: string; identity: Membership; grouping?: Membership};
type Route = {id: string; name?: string; source?: {node_id?: string}; destinations?: Array<{node_id?: string}>};
type AssessmentRow = {id: string; name: string; revision: number; technical_status: string; gaps: string[]; checks: Array<{id: string; kind: string; status: string; sample_count: number; deadline_ms?: number; freshness_ms?: number; observed_max_latency_ms?: number; observed_max_data_age_ms?: number; ftti_ms?: number; observations?: Array<{detection_ms: number; reaction_ms: number; observed_state: string; status: string}>}>; evidence_event_ids: string[]};
type SafetyData = {project_id: string; requirements: Requirement[]; functions: Array<{id: string; name: string; hardware_node_id?: string}>; routes: Route[]; hardware: Hardware[];
  profiles: Array<{standard: string; url: string}>; bundle: {sha256: string; payload: {snapshot_id: string; freshness: string; execution_status: string;
    assessment: {technical_status: string; requirements: AssessmentRow[]; limitations: string[]}}}};

const template: Configuration = {profile: {standard: 'ISO 26262', edition: '2018', domain: 'road_vehicle', applicability: 'UNRESOLVED', reason: 'Fachliche Anwendbarkeit festlegen', clause_refs: [], work_product_refs: []},
  hazard_ref: '', safety_goal_ref: '', route_ids: [], criteria: {required_protections: [], fault_cases: []}};
const protectionLabels: Record<string, string> = {CRC: 'CRC-Prüfung', SEQUENCE_COUNTER: 'Sequenzzähler', ALIVE_COUNTER: 'Alive-Counter', DATA_ID: 'Datenkennung', TIMEOUT_MONITOR: 'Timeout-Überwachung', FRESHNESS: 'Datenalter', SOURCE_AUTHENTICATION: 'Senderauthentifizierung'};
const faultLabels: Record<string, string> = {LOSS: 'Verlust', REPETITION: 'Wiederholung', CORRUPTION: 'Verfälschung', WRONG_SEQUENCE: 'Falsche Reihenfolge', TIMEOUT: 'Timeout', DELAY: 'Verzögerung', STALE_DATA: 'Veraltete Daten', LINK_DOWN: 'Verbindungsabbruch', QUEUE_OVERFLOW: 'Queue-Überlauf', WRONG_SENDER: 'Falscher Sender'};
const applicabilityLabels: Record<string, string> = {APPLICABLE: 'Anwendbar', NOT_APPLICABLE: 'Nicht anwendbar', UNRESOLVED: 'Noch zu klären'};
const lines = (value: string) => value.split('\n').map(item => item.trim()).filter(Boolean);

function RequirementFields({configuration, onChange, data, owner}: {configuration: Configuration; onChange: (next: Configuration) => void; data: SafetyData; owner: string}) {
  const [query, setQuery] = useState('');
  const [revisions, setRevisions] = useState(() => Object.entries(configuration.eip?.source_revisions ?? {}).map(([reference, revision]) => ({reference, revision})));
  const revisionInputs = useRef<Array<HTMLInputElement | null>>([]);
  useEffect(() => {
    revisions.forEach((item, index) => revisionInputs.current[index]?.setCustomValidity(
      revisions.filter(row => row.reference.trim() === item.reference.trim()).length > 1 ? 'Quellenreferenzen müssen eindeutig sein.' : ''));
  }, [revisions]);
  const hardware = useMemo(() => new Map((data.hardware ?? []).map(item => [item.id, item])), [data.hardware]);
  const functionHardware = data.functions.find(item => item.id === owner)?.hardware_node_id;
  const endpoints = (route: Route) => [route.source?.node_id, ...(route.destinations ?? []).map(item => item.node_id)].filter((id): id is string => Boolean(id));
  const groups = new Map<string, {label: string; frames: Map<string, {label: string; routes: Route[]}>}>();
  const normalizedQuery = query.toLocaleLowerCase();
  for (const route of data.routes) {
    const selected = configuration.route_ids.includes(route.id);
    if (functionHardware && !endpoints(route).includes(functionHardware) && !selected) continue;
    const sender = hardware.get(route.source?.node_id ?? '');
    const receiverNames = (route.destinations ?? []).map(item => hardware.get(item.node_id ?? '')?.name ?? 'Empfänger nicht zugeordnet');
    const identity = sender?.grouping ?? sender?.identity;
    const clusterKey = identity?.cluster_id ?? 'unassigned';
    const clusterLabel = identity?.cluster_name ?? (identity?.cluster_id ? 'Benanntes Cluster' : 'Cluster nicht zugeordnet');
    const frameKey = identity?.system_owner_id ?? identity?.systemOwnerId ?? 'unassigned';
    const frameLabel = hardware.get(frameKey)?.name ?? 'Systemrahmen nicht zugeordnet';
    if (normalizedQuery && ![route.name, sender?.name, ...receiverNames, clusterLabel, frameLabel].join(' ').toLocaleLowerCase().includes(normalizedQuery)) continue;
    if (!groups.has(clusterKey)) groups.set(clusterKey, {label: clusterLabel, frames: new Map()});
    const frames = groups.get(clusterKey)!.frames;
    if (!frames.has(frameKey)) frames.set(frameKey, {label: frameLabel, routes: []});
    frames.get(frameKey)!.routes.push(route);
  }
  const scopedHardware = Array.from(new Set(data.routes.filter(item => configuration.route_ids.includes(item.id)).flatMap(endpoints)));
  const profile = configuration.profile, criteria = configuration.criteria;
  const changeProfile = (next: Partial<Configuration['profile']>) => onChange({...configuration, profile: {...profile, ...next}});
  const changeCriteria = (next: Partial<Configuration['criteria']>) => onChange({...configuration, criteria: {...criteria, ...next}});
  const updateFault = (index: number, next: Partial<FaultCase>) => changeCriteria({fault_cases: (criteria.fault_cases ?? []).map((item, row) => row === index ? {...item, ...next} : item)});
  function updateRevisions(next: typeof revisions) {
    setRevisions(next);
    if (configuration.eip) onChange({...configuration, eip: {...configuration.eip, source_revisions: Object.fromEntries(next.map(item => [item.reference, item.revision]))}});
  }
  return <>
    <fieldset className={styles.section}><legend>Norm und Anwendbarkeit</legend><div className={styles.fields}>
      <label>Norm<select value={profile.standard} onChange={event => changeProfile({standard: event.target.value, edition: ''})}>{data.profiles.map(item => <option key={item.standard}>{item.standard}</option>)}{!data.profiles.some(item => item.standard === profile.standard) && <option>{profile.standard}</option>}</select></label>
      <label>Ausgabe / Änderungsserie<input required maxLength={500} value={profile.edition} onChange={event => changeProfile({edition: event.target.value})} /></label>
      <label>Anwendungsbereich<input required maxLength={500} value={profile.domain} onChange={event => changeProfile({domain: event.target.value})} /></label>
      <label>Anwendbarkeit<select value={profile.applicability} onChange={event => changeProfile({applicability: event.target.value})}>{Object.entries(applicabilityLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label className={styles.wide}>Begründung<textarea required maxLength={500} rows={2} value={profile.reason} onChange={event => changeProfile({reason: event.target.value})} /></label>
      <label>Normabschnitte · eine Referenz je Zeile<textarea rows={3} value={(profile.clause_refs ?? []).join('\n')} onChange={event => changeProfile({clause_refs: event.target.value.split('\n')})} /></label>
      <label>Arbeitsergebnisse · eine Referenz je Zeile<textarea rows={3} value={(profile.work_product_refs ?? []).join('\n')} onChange={event => changeProfile({work_product_refs: event.target.value.split('\n')})} /></label>
    </div></fieldset>
    <fieldset className={styles.section}><legend>Gefährdung und Sicherheitsziel</legend><div className={styles.fields}>
      <label>Gefährdungsreferenz<input required maxLength={500} value={configuration.hazard_ref} onChange={event => onChange({...configuration, hazard_ref: event.target.value})} /></label>
      <label>Sicherheitszielreferenz<input required maxLength={500} value={configuration.safety_goal_ref} onChange={event => onChange({...configuration, safety_goal_ref: event.target.value})} /></label>
    </div><label className={styles.check}><input type="checkbox" checked={Boolean(configuration.integrity)} onChange={event => onChange({...configuration, integrity: event.target.checked ? {model: '', level: '', decision_ref: ''} : undefined})} />Fachlich bestätigte Integritätsentscheidung hinterlegen</label>
      {configuration.integrity && <div className={styles.fields}>{(['model', 'level', 'decision_ref'] as const).map((field, index) => <label key={field}>{['Bewertungsmodell (z. B. ASIL)', 'Bestätigte Einstufung', 'Entscheidungsreferenz'][index]}<input required maxLength={500} value={configuration.integrity![field]} onChange={event => onChange({...configuration, integrity: {...configuration.integrity!, [field]: event.target.value}})} /></label>)}</div>}
    </fieldset>
    <fieldset className={styles.section}><legend>Kommunikationsrouten</legend><p>Nach Sendercluster und Systemrahmen gruppiert. {configuration.route_ids.length} von maximal 32 Routen ausgewählt.</p>
      <label>Routen suchen<input type="search" placeholder="Cluster, Systemrahmen, Sender oder Empfänger …" value={query} onChange={event => setQuery(event.target.value)} /></label>
      <div className={styles.routes}>{Array.from(groups).sort((a, b) => a[1].label.localeCompare(b[1].label, 'de')).map(([key, group]) => <details key={key} open={Boolean(query) || group.frames.size === 1}>
        <summary>{group.label}<span>{Array.from(group.frames.values()).reduce((sum, frame) => sum + frame.routes.length, 0)} Routen</span></summary>
        {Array.from(group.frames).sort((a, b) => a[1].label.localeCompare(b[1].label, 'de')).map(([frameKey, frame]) => <div className={styles.frame} key={frameKey}><h4>{frame.label}</h4>{frame.routes.sort((a, b) => (a.name ?? '').localeCompare(b.name ?? '', 'de')).map(route => {
          const selected = configuration.route_ids.includes(route.id), sender = hardware.get(route.source?.node_id ?? '');
          const targets = (route.destinations ?? []).map(item => hardware.get(item.node_id ?? ''));
          return <label className={styles.route} key={route.id}><input type="checkbox" checked={selected} disabled={!selected && configuration.route_ids.length >= 32} onChange={event => onChange({...configuration, route_ids: event.target.checked ? [...configuration.route_ids, route.id] : configuration.route_ids.filter(id => id !== route.id)})} />
            <span><strong>{sender?.name ?? 'Sender nicht zugeordnet'} → {targets.map(item => item?.name ?? 'Empfänger nicht zugeordnet').join(', ')}</strong>
              <small>{route.name || 'Kommunikationsroute'}{targets.some(item => (item?.grouping ?? item?.identity)?.cluster_id !== (sender?.grouping ?? sender?.identity)?.cluster_id) && <> · Zielcluster: {Array.from(new Set(targets.map(item => (item?.grouping ?? item?.identity)?.cluster_name ?? 'Nicht zugeordnet'))).join(', ')}</>}</small></span></label>;
        })}</div>)}
      </details>)}</div>
      {!groups.size && <p>Keine passenden Routen. Wähle zuerst die verantwortliche Funktion oder ändere die Suche.</p>}
      {configuration.route_ids.filter(id => !data.routes.some(route => route.id === id)).map(id => <p key={id} role="alert">Eine gespeicherte Route ist nicht mehr verfügbar. <button type="button" className="button secondary tiny" onClick={() => onChange({...configuration, route_ids: configuration.route_ids.filter(item => item !== id)})}>Referenz entfernen</button></p>)}
    </fieldset>
    <fieldset className={styles.section}><legend>Prüfgrenzen und Schutzmechanismen</legend><p>Nur ausdrücklich bestätigte Grenzen eintragen. Leere Felder bleiben offen.</p><div className={styles.fields}>
      {(['deadline_ms', 'freshness_ms'] as const).map((field, index) => <label key={field}>{['E2E-Frist (ms)', 'Maximales Datenalter (ms)'][index]}<input type="number" min={0} step="any" value={criteria[field] ?? ''} onChange={event => changeCriteria({[field]: event.target.value === '' ? undefined : Number(event.target.value)})} /></label>)}
    </div><div className={styles.checks}>{Object.entries(protectionLabels).map(([value, label]) => <label className={styles.check} key={value}><input type="checkbox" checked={(criteria.required_protections ?? []).includes(value)} onChange={event => changeCriteria({required_protections: event.target.checked ? [...(criteria.required_protections ?? []), value] : (criteria.required_protections ?? []).filter(item => item !== value)})} />{label}</label>)}</div>
    </fieldset>
    <fieldset className={styles.section}><legend>Fehlerfälle und sichere Reaktion</legend>{(criteria.fault_cases ?? []).map((fault, index) => <div className={styles.fault} key={index}><div className={styles.fields}>
      <label>Fallreferenz<input required maxLength={200} value={fault.id} onChange={event => updateFault(index, {id: event.target.value})} /></label>
      <label>Fehlerart<select value={fault.type} onChange={event => updateFault(index, {type: event.target.value})}>{Object.entries(faultLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>FTTI (ms)<input required type="number" min={0} step="any" value={fault.ftti_ms} onChange={event => updateFault(index, {ftti_ms: event.target.value === '' ? '' : Number(event.target.value)})} /></label>
      <label>Erkennungsfrist (ms)<input required type="number" min={0} step="any" value={fault.detection_ms} onChange={event => updateFault(index, {detection_ms: event.target.value === '' ? '' : Number(event.target.value)})} /></label>
      <label>Beobachteter Empfänger<select required value={fault.receiver_id} onChange={event => updateFault(index, {receiver_id: event.target.value})}><option value="">Bitte auswählen</option>{scopedHardware.map(id => <option key={id} value={id}>{hardware.get(id)?.name ?? 'Nicht zugeordnet'}</option>)}{fault.receiver_id && !scopedHardware.includes(fault.receiver_id) && <option value={fault.receiver_id}>{hardware.get(fault.receiver_id)?.name ?? 'Gespeicherter Empfänger'} · außerhalb der Routenauswahl</option>}</select></label>
      <label>Sicherer Zustand<input required maxLength={500} value={fault.safe_state} onChange={event => updateFault(index, {safe_state: event.target.value})} /></label>
    </div><button className="button secondary tiny" type="button" onClick={() => changeCriteria({fault_cases: criteria.fault_cases!.filter((_, row) => row !== index)})}>Fehlerfall entfernen</button></div>)}
      <button className="button secondary" type="button" disabled={(criteria.fault_cases ?? []).length >= 32} onClick={() => changeCriteria({fault_cases: [...(criteria.fault_cases ?? []), {id: '', type: 'LOSS', ftti_ms: '', detection_ms: '', safe_state: '', receiver_id: ''}]})}>Fehlerfall hinzufügen</button>
    </fieldset>
    <fieldset className={styles.section}><legend>EIP-Quellenbezug</legend><label className={styles.check}><input type="checkbox" checked={Boolean(configuration.eip)} onChange={event => {setRevisions([]); onChange({...configuration, eip: event.target.checked ? {project_id: '', requirement_ref: '', source_revisions: {}} : undefined});}} />Originale EIP-Quellenrevisionen hinterlegen</label>
      {configuration.eip && <><div className={styles.fields}><label>EIP-Projekt<input required maxLength={200} value={configuration.eip.project_id} onChange={event => onChange({...configuration, eip: {...configuration.eip!, project_id: event.target.value}})} /></label><label>Anforderungsreferenz<input required maxLength={200} value={configuration.eip.requirement_ref} onChange={event => onChange({...configuration, eip: {...configuration.eip!, requirement_ref: event.target.value}})} /></label></div>
        {revisions.map((item, index) => <div className={styles.revision} key={index}><label>Quellenreferenz<input ref={node => {revisionInputs.current[index] = node;}} required maxLength={200} value={item.reference} onChange={event => updateRevisions(revisions.map((row, position) => position === index ? {...row, reference: event.target.value} : row))} /></label><label>Originale Revision<input required type="number" min={1} step={1} value={item.revision} onChange={event => updateRevisions(revisions.map((row, position) => position === index ? {...row, revision: Number(event.target.value)} : row))} /></label><button className="button secondary tiny" type="button" onClick={() => updateRevisions(revisions.filter((_, position) => position !== index))}>Entfernen</button></div>)}
        {new Set(revisions.map(item => item.reference)).size !== revisions.length && <p role="alert">Quellenreferenzen müssen eindeutig sein.</p>}
        <button className="button secondary" type="button" disabled={revisions.length >= 20} onClick={() => updateRevisions([...revisions, {reference: '', revision: 1}])}>Quelle hinzufügen</button>
      </>}
    </fieldset>
  </>;
}

export function SafetyAssurancePanel() {
  const [data, setData] = useState<SafetyData | null>(null), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<Requirement | null>(null), [name, setName] = useState(''), [owner, setOwner] = useState('');
  const [configuration, setConfiguration] = useState<Configuration>(template), [open, setOpen] = useState(false);
  const [editorSession, setEditorSession] = useState(0);
  const editProject = useRef('');
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
    editProject.current = readActiveProjectId();
    setEditorSession(value => value + 1);
    setConfiguration(structuredClone(row?.configuration ?? template)); setOpen(true);
  }
  async function save() {
    const project = readActiveProjectId(); setBusy(true); setError('');
    try {
      if (project !== editProject.current || project !== loadedProject.current) throw new Error('Das Projekt hat gewechselt. Bitte die Anforderung neu öffnen.');
      const savedConfiguration = {...configuration, profile: {...configuration.profile,
        clause_refs: lines((configuration.profile.clause_refs ?? []).join('\n')),
        work_product_refs: lines((configuration.profile.work_product_refs ?? []).join('\n'))}};
      const response = await fetch(`/api/engineering/safety-requirements${editing ? '/' + encodeURIComponent(editing.id) : ''}`, {
        method: editing ? 'PATCH' : 'POST', headers: {'Content-Type': 'application/json', 'X-Project-ID': project},
        body: JSON.stringify({name, function_id: owner, configuration: savedConfiguration, ...(editing ? {expected_version: editing.version} : {})})});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Anforderung konnte nicht gespeichert werden.');
      if (project === readActiveProjectId()) {setOpen(false); await load(); notifyWorkflowChanged();}
    } catch (cause) {setError(cause instanceof Error ? cause.message : 'Ungültige Anforderung.');} finally {setBusy(false);}
  }
  const payload = data?.bundle.payload;
  return <section className={`panel safety-assurance-panel ${styles.panel}`} aria-labelledby="safety-assurance-title">
    <header className="intelligence-toolbar"><div><p className="eyebrow">Safety & Regulatory Assurance</p><h2 id="safety-assurance-title">Sicherheitsanforderungen und Prüfbelege</h2></div>
      <div className="analysis-actions"><button className="button secondary" type="button" disabled={busy || !data} onClick={() => edit(null)}>Anforderung erfassen</button>
        {data && <a className="button secondary" href={`/api/engineering/intelligence/safety?project=${encodeURIComponent(data.project_id)}&download=1`} download>Belege für EIP exportieren</a>}</div></header>
    <p>ISO 26262, UN R155 und UN R156 erhalten eigene Anwendbarkeit, Ausgabe und Nachweiskette. Technische Ergebnisse erteilen keine Norm-, ASIL- oder Typgenehmigungsfreigabe.</p>
    {error && <p role="alert">{error} <button type="button" onClick={() => void load()}>Neu laden</button></p>}
    <dl className={`intelligence-counts ${styles.counts}`}><div><dt>Technische Prüfung</dt><dd>{payload?.freshness === 'CURRENT' ? payload.assessment.technical_status : 'NOT_EVALUATED'}</dd></div>
      <div><dt>Belegstand</dt><dd>{payload?.freshness ?? 'Nicht geladen'}</dd></div><div><dt>Normative Vollständigkeit</dt><dd>NOT_EVALUATED</dd></div><div><dt>Fachliche Freigabe</dt><dd>Unabhängiges Review in EIP erforderlich</dd></div></dl>
    {data && !data.requirements.length && <p>Keine Sicherheitsanforderungen erfasst. Fristen, ASIL und FTTI werden nicht automatisch zugewiesen.</p>}
    {Boolean(data?.requirements.length) && <div className="table-scroll"><table><thead><tr><th>Anforderung</th><th>Funktion</th><th>Norm / Ausgabe</th><th>Anwendbarkeit</th><th>Revision</th><th>Aktion</th></tr></thead>
      <tbody>{data?.requirements.map(row => {const profile = row.configuration.profile as {standard: string; edition: string; applicability: string}; return <tr key={row.id}>
        <td>{row.name}</td><td>{data.functions.find(item => item.id === row.function_id)?.name ?? 'Verknüpfung fehlt'}</td><td>{profile.standard} · {profile.edition}</td><td>{applicabilityLabels[profile.applicability] ?? profile.applicability}</td><td>{row.version}</td><td><button type="button" className="button secondary tiny" disabled={busy} onClick={() => edit(row)}>Bearbeiten</button></td></tr>;})}</tbody></table></div>}
    {payload?.assessment.requirements.map(row => <details key={row.id}><summary>{row.name} · eingefrorene Revision {row.revision} · {row.technical_status}{payload.freshness !== 'CURRENT' ? ' · historisch' : ''}</summary>
      <table><thead><tr><th>Prüfung</th><th>Art</th><th>Ergebnis</th><th>Stichproben</th><th>Messwerte / Grenzen</th></tr></thead><tbody>{row.checks.map(check => <tr key={check.kind + check.id}><td>{check.id}</td><td>{check.kind}</td><td>{check.status}</td><td>{check.sample_count}</td><td>{check.kind === 'COMMUNICATION'
        ? <>E2E: {check.observed_max_latency_ms ?? '—'} / {check.deadline_ms ?? '—'} ms · Alter: {check.observed_max_data_age_ms ?? '—'} / {check.freshness_ms ?? '—'} ms</>
        : <>FTTI: {check.ftti_ms ?? '—'} ms{check.observations?.map((observation, index) => <p key={index}>Erkennung {observation.detection_ms} ms · Reaktion {observation.reaction_ms} ms · {observation.observed_state} · {observation.status}</p>)}</>}</td></tr>)}</tbody></table>
      <ul>{row.gaps.map(gap => <li key={gap}>{gap}</li>)}</ul><details><summary>Originale Ereignisbelege</summary><p>{row.evidence_event_ids.join(', ') || 'Keine korrelierten Belege'}</p></details></details>)}
    <details><summary>Normquellen und Bewertungsumfang</summary><ul>{data?.profiles.map(profile => <li key={profile.standard}><a href={profile.url} target="_blank" rel="noopener noreferrer">{profile.standard}</a></li>)}</ul>
      <p>Das Quellenverzeichnis führt die Normreferenzen mit getrennten Rechtehinweisen. Ausgabe und Änderungsserie müssen für jedes Projekt fachlich bestätigt werden.</p></details>
    {open && data && <details open className={styles.editor}><summary>Anforderung {editing ? 'bearbeiten' : 'erfassen'}</summary><form onSubmit={event => {event.preventDefault(); void save();}}>
      <fieldset disabled={busy} className={styles.editorBody}><div className={styles.fields}><label>Name<input value={name} onChange={event => setName(event.target.value)} required maxLength={300} /></label>
        <label>Funktion<select required value={owner} onChange={event => setOwner(event.target.value)}><option value="">Bitte auswählen</option>{data?.functions.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
        </div><p>Verknüpfe Gefährdung, Sicherheitsziel, Routen und ausdrücklich bestätigte Prüfgrenzen. Fehlende Nachweise bleiben offen.</p>
        <RequirementFields key={editorSession} configuration={configuration} onChange={setConfiguration} data={data} owner={owner} />
        <div className={styles.actions}><button className="button primary" type="submit">{busy ? 'Speichern …' : 'Anforderung speichern'}</button><button className="button secondary" type="button" onClick={() => setOpen(false)}>Schließen</button></div></fieldset>
    </form></details>}
  </section>;
}

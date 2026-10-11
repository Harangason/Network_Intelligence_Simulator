"use client";

import { useEffect, useRef, useState } from 'react';
import { publishEngineeringModelChanged } from '@/lib/engineering-events';
import styles from './goal-hardware-facts.module.css';

type Capability = { id: string; hardware_node_ref: string; technology: string; supported: boolean; controller_count: number; max_channels: number; max_ports: number; supported_bitrates: number[]; [key: string]: unknown };
type Controller = { id: string; hardware_node_ref: string; technology: string; max_channels: number; active_channels: number[]; status: string; [key: string]: unknown };
type Interface = { id: string; name: string; technology: string; controller_ref?: string; channel_index?: number; network_ref?: string };
type Hardware = { id: string; name: string; capabilities: Capability[]; controllers: Controller[]; interfaces: Interface[] };
type Inventory = { model_revision: string; hardware: Hardware[]; technologies: string[]; status: string };
type ControllerDraft = { value: Controller; max: string; reserved: string };
const normalize = (value: string) => value.toLowerCase().replaceAll(/[^a-z0-9]/g, '').replace('automotiveethernet', 'ethernet');
// getRandomValues also works on the local HTTP LAN preview.
const factId = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join('');
function numbers(text: string) {
  if (!text.trim()) return [];
  const values = text.split(/[,;\s]+/).filter(Boolean).map(Number);
  if (values.some(value => !Number.isFinite(value) || value <= 0)) throw new Error('Zahlen müssen größer als null sein. Mit Komma oder Leerzeichen trennen.');
  return values;
}

function FactForm({ inventory, hardware, technology, projectId, workloadId, onSaved }: { inventory: Inventory; hardware: Hardware; technology: string; projectId: string; workloadId: string; onSaved: () => void }) {
  const matches = (value: string) => normalize(value) === normalize(technology);
  const capabilities = hardware.capabilities.filter(c => matches(c.technology));
  const existing = capabilities[0];
  const interfaces = hardware.interfaces.filter(i => matches(i.technology));
  const [supported, setSupported] = useState(existing ? String(existing.supported) : '');
  const [count, setCount] = useState(existing ? String(existing.controller_count) : '');
  const [channels, setChannels] = useState(existing ? String(existing.max_channels) : '');
  const [ports, setPorts] = useState(existing ? String(existing.max_ports) : '');
  const [bitrates, setBitrates] = useState(existing?.supported_bitrates.join(', ') ?? '');
  const [controllers, setControllers] = useState<ControllerDraft[]>(() => hardware.controllers.filter(c => matches(c.technology)).map(value => ({value, max: String(value.max_channels), reserved: value.active_channels.join(', ')})));
  const [assignments, setAssignments] = useState(() => interfaces.map(i => ({interface_ref: i.id, controller_ref: i.controller_ref ?? '', channel_index: i.channel_index ? String(i.channel_index) : ''})));
  const [evidence, setEvidence] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const reservedIds = new Set(hardware.controllers.map(c => c.id));
  async function save() {
    setBusy(true); setError('');
    try {
      const rates = numbers(bitrates);
      if (supported === 'true' && !rates.length) throw new Error('Mindestens eine bestätigte Bitrate angeben.');
      const body = { expected_revision: inventory.model_revision, evidence,
        capability: {...existing, id: existing?.id ?? `cap-${factId()}`, hardware_node_ref: hardware.id, technology,
          supported: supported === 'true', controller_count: Number(count), max_channels: Number(channels), max_ports: Number(ports), supported_bitrates: rates},
        controllers: controllers.map(c => ({...c.value, max_channels: Number(c.max), active_channels: numbers(c.reserved)})),
        assignments: assignments.map(a => ({...a, channel_index: Number(a.channel_index)})),
      };
      const session = await fetch('/api/engineering/agent/review-session', {cache: 'no-store'}).then(r => r.json());
      const response = await fetch(`/api/engineering/agent/execution-goals/${encodeURIComponent(workloadId)}/hardware-facts`, {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-Project-ID': projectId, 'X-Human-Review': 'confirmed', 'X-Review-CSRF': session.csrf_token}, body: JSON.stringify(body),
      });
      const result = await response.json();
      if (!response.ok || !result.success) throw new Error(result.error ?? result.findings?.[0]?.message ?? 'Hardwaredaten konnten nicht gespeichert werden.');
      publishEngineeringModelChanged({resource: 'hardware-nodes', id: hardware.id, name: hardware.name}); onSaved();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Speichern fehlgeschlagen.'); }
    finally { setBusy(false); }
  }
  return <form className={styles.form} onSubmit={event => { event.preventDefault(); void save(); }}>
    <p>Bestätige die tatsächliche Ausstattung von <strong>{hardware.name}</strong>. Vorhandene Netze und Anschlüsse bleiben erhalten. Die Anschlussstrategie wird anschließend neu geprüft.</p>
    <fieldset disabled={busy || capabilities.length > 1}>
      <legend>1 · Bestätigte Hardwaregrenzen · {technology}</legend>
      <label>Technologie unterstützt<select required value={supported} onChange={e => setSupported(e.target.value)}><option value="">Bitte angeben</option><option value="true">Ja</option><option value="false">Nein</option></select></label>
      <div className={styles.grid}>
        <label>Controller maximal<input required type="number" min="0" max="64" step="1" value={count} onChange={e => setCount(e.target.value)} /></label>
        <label>Kanäle insgesamt<input required type="number" min="0" step="1" value={channels} onChange={e => setChannels(e.target.value)} /></label>
        <label>Physische Ports maximal<input required type="number" min="0" step="1" value={ports} onChange={e => setPorts(e.target.value)} /></label>
      </div>
      <label>Unterstützte Bitraten in bit/s<input required={supported === 'true'} value={bitrates} onChange={e => setBitrates(e.target.value)} placeholder="Werte aus Hardwaredokumentation" /></label>
    </fieldset>
    <fieldset disabled={busy}>
      <legend>2 · Vorhandene Controller</legend>
      <p>Nur tatsächlich vorhandene Controller erfassen. Reservierte Kanäle sind weitere bereits belegte Kanäle; freie Kanäle bleiben ungenannt.</p>
      {controllers.map((c, index) => <section key={c.value.id} className={styles.controller}>
        <strong>Controller {index + 1}</strong>
        <details><summary>Controllerkennung</summary><small>{c.value.id}</small></details>
        <div className={styles.grid}><label>Kanäle maximal<input required type="number" min="0" step="1" value={c.max} onChange={e => setControllers(current => current.map((item, n) => n === index ? {...item, max: e.target.value} : item))} /></label>
          <label>Status<select value={c.value.status} onChange={e => setControllers(current => current.map((item, n) => n === index ? {...item, value: {...item.value, status: e.target.value}} : item))}><option value="ACTIVE">Verfügbar</option><option value="PLANNED">Geplant</option><option value="UNAVAILABLE">Nicht verfügbar</option><option value="OUTDATED">Veraltet</option></select></label></div>
        <label>Weitere reservierte Kanalnummern<input value={c.reserved} onChange={e => setControllers(current => current.map((item, n) => n === index ? {...item, reserved: e.target.value} : item))} /></label>
        {!reservedIds.has(c.value.id) && <button type="button" onClick={() => setControllers(current => current.filter((_, n) => n !== index))}>Controllerangabe entfernen</button>}
      </section>)}
      <button type="button" disabled={controllers.length >= 64} onClick={() => setControllers(current => [...current, {value: {id: `controller-${factId()}`, hardware_node_ref: hardware.id, technology, max_channels: 0, active_channels: [], status: 'ACTIVE'}, max: '', reserved: ''}])}>Vorhandenen Controller erfassen</button>
    </fieldset>
    {!!interfaces.length && <fieldset disabled={busy}><legend>3 · Vorhandene Anschlüsse zuordnen</legend>
      {interfaces.map((item, index) => <section className={styles.controller} key={item.id}><strong>{item.name}</strong><small>Netz: {item.network_ref ?? 'Nicht zugeordnet'}</small>
        <label>Controller für {item.name}<select required value={assignments[index].controller_ref} onChange={e => setAssignments(current => current.map((a, n) => n === index ? {...a, controller_ref: e.target.value} : a))}><option value="">Bitte zuordnen</option>{controllers.map((c, n) => <option key={c.value.id} value={c.value.id}>Controller {n + 1} · {c.value.id}</option>)}</select></label>
        <label>Kanal für {item.name}<input required type="number" min="1" step="1" value={assignments[index].channel_index} onChange={e => setAssignments(current => current.map((a, n) => n === index ? {...a, channel_index: e.target.value} : a))} /></label>
      </section>)}
    </fieldset>}
    <label>Nachweis / Quelle<textarea required minLength={3} maxLength={2000} value={evidence} onChange={e => setEvidence(e.target.value)} placeholder="Zum Beispiel Datenblatt und Revision oder geprüfte Bestandsaufnahme" /></label>
    <label className={styles.confirm}><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />Die Angaben beschreiben die geprüfte tatsächliche Hardware.</label>
    <button type="submit" disabled={busy || !confirmed || capabilities.length > 1}>Hardwaredaten bestätigen &amp; Auftrag fortsetzen</button>
    {capabilities.length > 1 && <p role="alert">Mehrere widersprüchliche Hardwaregrenzen sind vorhanden. Diese müssen zuerst eindeutig geklärt werden.</p>}
    {error && <p role="alert">{error}</p>}
  </form>;
}

export function GoalHardwareFacts({ projectId, workloadId, onContinue }: {projectId: string; workloadId: string; onContinue?: () => void}) {
  const [open, setOpen] = useState(false);
  const [inventory, setInventory] = useState<Inventory | null>(null);
  const [owner, setOwner] = useState('');
  const [technology, setTechnology] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), [projectId, workloadId]);
  async function load() {
    request.current?.abort(); const controller = new AbortController(); request.current = controller;
    setOpen(true); setLoading(true); setError(''); setInventory(null);
    try {
      const response = await fetch(`/api/engineering/agent/execution-goals/${encodeURIComponent(workloadId)}/hardware-facts`, {headers: {'X-Project-ID': projectId}, cache: 'no-store', signal: controller.signal});
      const result = await response.json();
      if (!response.ok || !result.success) throw new Error(result.findings?.[0]?.message ?? 'Hardwaredaten konnten nicht geladen werden.');
      setInventory(result.data); setOwner(result.data.hardware[0]?.id ?? ''); setTechnology(result.data.technologies[0] ?? '');
    } catch (cause) { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Laden fehlgeschlagen.'); }
    finally { if (!controller.signal.aborted) setLoading(false); }
  }
  const hardware = inventory?.hardware.find(h => h.id === owner);
  return <section className={styles.panel}>
    <button type="button" onClick={() => void load()} disabled={loading || !onContinue}>{loading ? 'Hardwaredaten werden geladen …' : 'Fehlende Hardwaredaten ergänzen'}</button>
    {open && <><button type="button" onClick={() => setOpen(false)}>Schließen</button>
      {inventory && <><label>Hardware<select value={owner} onChange={e => setOwner(e.target.value)}>{inventory.hardware.map(h => <option key={h.id} value={h.id}>{h.name}</option>)}</select></label>
        <label>Technologie<select value={technology} onChange={e => setTechnology(e.target.value)}>{inventory.technologies.map(t => <option key={t}>{t}</option>)}</select></label></>}
      {inventory && hardware && technology && <FactForm key={`${inventory.model_revision}:${owner}:${technology}`} inventory={inventory} hardware={hardware} technology={technology} projectId={projectId} workloadId={workloadId} onSaved={() => {setOpen(false); onContinue?.();}} />}
      {error && <p role="alert">{error}</p>}
    </>}
  </section>;
}

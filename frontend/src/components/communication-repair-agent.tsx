"use client";

import { useEffect, useRef, useState } from "react";
import { readActiveProjectId } from "@/lib/user-settings";
import { notifyWorkflowChanged } from "./workflow-header";

type FunctionPartner = { function_id: string | null; function: string; hardware: string; evidence: string; issue: string | null };
type FunctionalFlow = { id: string; code: string; source: FunctionPartner; destinations: FunctionPartner[]; issues: string[]; changed: boolean };
type Option = { id: string; label: string; questions: string[]; action: 'adopt' | 'restore'; comparison: { id: string; code: string; name: string; before: string; after: string; functions?: FunctionalFlow }[] };
type RepairGroup = { id: string; status: "AUTO" | "QUESTION" | "BLOCKED"; reason: string; options: Option[];
  connections: { device: string; old_port: string }[]; restore_unavailable?: string;
  routes: { id: string; name: string; code: string }[]; messages: { id: string; name: string }[] };
type Plan = { token: string; groups: RepairGroup[]; architecture?: { hardware_nodes: number; physical_networks: number; functions: number; communications: number; resolved: number; device_io: number; unresolved: FunctionalFlow[]; flows: FunctionalFlow[] } };
type Applied = { id: string; routes: number; messages: number; label: string };
type Result = { plan: Plan; applied: Applied[] };

async function request<T>(action: string, project: string, body: unknown): Promise<T> {
  const response = await fetch(`/api/engineering/workflow/communication-repair/${action}`, {
    method: "POST", headers: { "Content-Type": "application/json", "X-Project-ID": project }, body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error ?? "Die Kommunikationsverknüpfungen konnten nicht repariert werden.");
  return data;
}

export function CommunicationRepairAgent({ onChanged }: { onChanged: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const project = useRef("");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [applied, setApplied] = useState<Applied[]>([]);
  const [deferred, setDeferred] = useState<Set<string>>(new Set());
  const launched = useRef(false);
  useEffect(() => {
    if (!launched.current && new URLSearchParams(window.location.search).get('assistant') === 'repair') {
      launched.current = true;
      void start();
    }
  }, []);

  function accept(result: Result) {
    setPlan(result.plan);
    setApplied(previous => [...previous, ...result.applied]);
    if (result.applied.length) { onChanged(); notifyWorkflowChanged(); window.dispatchEvent(new Event('engineering:write-completed')); }
  }

  async function start() {
    dialog.current?.showModal();
    project.current = readActiveProjectId();
    setBusy(true); setError(""); setPlan(null); setApplied([]); setDeferred(new Set());
    try {
      const next = await request<Plan>("preview", project.current, {});
      setPlan(next);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Reparatur fehlgeschlagen."); }
    finally { setBusy(false); }
  }

  async function choose(group: RepairGroup, option: Option) {
    if (!plan) return;
    if (readActiveProjectId() !== project.current) { setError('Das aktive Projekt wurde gewechselt. Bitte erneut prüfen.'); return; }
    setBusy(true); setError("");
    try { accept(await request<Result>("apply", project.current, { token: plan.token, choices: { [group.id]: option.id } })); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Reparatur fehlgeschlagen."); }
    finally { setBusy(false); }
  }

  return <>
    <button className="button secondary eng-repair-agent-button" type="button" onClick={() => void start()} title="Neue Signalwege mit der bisherigen Führung vergleichen und auswählen">
      <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M7 7h10v10H7zM12 3v4M3 12h4m10 0h4M12 17v4" /><circle cx="12" cy="12" r="2" /></svg>
      Reparatur-Agent
    </button>
    <dialog ref={dialog} className="eng-repair-agent-dialog" aria-label="Reparatur-Agent für Kommunikation" onCancel={event => { if (busy) event.preventDefault(); }}>
      <header><div><p className="eyebrow">Kommunikationsverknüpfungen</p><h3>Reparatur-Agent</h3></div>
        <button className="button secondary tiny" type="button" disabled={busy} aria-label="Reparatur-Agent schließen" onClick={() => dialog.current?.close()}>×</button></header>
      <p>Die aktuelle Hardwarearchitektur bestimmt die neuen Wege. Ausgangspunkt ist die bisherige Kommunikation zwischen Funktionen: Wer sendet welche Nachricht an welche Partnerfunktion? Deine Auswahl setzt diese Kommunikation auf den aktuellen Geräten und Anschlüssen um und aktualisiert die Routing-Tabelle.</p>
      {plan?.architecture && <section className="eng-repair-architecture"><strong>Aktuelle Architektur und Funktionspartner</strong>
        <p>{plan.architecture.hardware_nodes} Geräte · {plan.architecture.physical_networks} Netze · {plan.architecture.functions} Funktionen<br />
          {plan.architecture.resolved} von {plan.architecture.communications} Kommunikationsbeziehungen zugeordnet · davon {plan.architecture.device_io} mit Geräte-I/O</p>
        <details><summary>Kommunikation zwischen Funktionen prüfen</summary>
          <div className="eng-repair-comparison"><table><thead><tr><th>Route</th><th>Sendende Funktion / Gerät</th><th>Empfangende Funktionen / Geräte</th></tr></thead><tbody>
            {plan.architecture.flows.map(flow => <tr key={flow.id}><th scope="row">{flow.code}</th><td>{flow.source.function}<small>{flow.source.hardware}</small></td><td>{flow.destinations.map((partner, i) => <div key={partner.function_id ?? i}>{partner.function}<small>{partner.hardware}</small></div>)}{flow.issues.map(issue => <p className="inline-error" key={issue}>{issue}</p>)}</td></tr>)}
          </tbody></table></div>
        </details>
        {plan.architecture.unresolved.length > 0 && <p>Bei {plan.architecture.unresolved.length} Beziehungen ist die Partnerfunktion oder ihre aktuelle Zuordnung noch zu klären. Der Agent ersetzt sie nicht durch ein erreichbares Nachbargerät.</p>}
      </section>}
      {busy && <p role="status">{plan ? 'Gewählte Führung prüfen und speichern …' : 'Anschlüsse und bisherige sowie neue Wege prüfen …'}</p>}
      {error && <p className="inline-error" role="alert">{error}</p>}
      {applied.length > 0 && <section className="eng-repair-success"><strong>Verknüpfungen repariert</strong>
        <ul>{applied.map(item => <li key={item.id}>{item.label} · {item.routes} Routen · {item.messages} Nachrichten</li>)}</ul>
        <p>Geänderte Routen sind technisch geprüft und benötigen eine erneute Freigabe. Kapazität und Timing anschließend neu bewerten.</p></section>}
      {!busy && plan?.groups.length === 0 && <p role="status">Keine weiteren reparierbaren Kommunikationsverknüpfungen gefunden. Freie Anschlüsse ohne Nachrichten sowie andere Parameterfehler werden nicht automatisch zugeordnet.</p>}
      {plan?.groups.map(group => <section className="eng-repair-group" key={group.id}>
        <h4>{group.connections.map(c => c.device).filter((value, index, values) => values.indexOf(value) === index).join(" · ")}</h4>
        <p>{group.reason}</p>
        <p className="muted">Bisher: {group.connections.map(c => c.old_port).join(" · ")}</p>
        {group.routes.length > 0 && <details><summary>{group.routes.length} betroffene Routen</summary><ul>{group.routes.map(r => <li key={r.id}>{r.code} · {r.name}</li>)}</ul></details>}
        {deferred.has(group.id) ? <p role="status">Offen gelassen. Die bestehende Funktionskommunikation wurde nicht umgehängt. Nach der Änderung im Netzwerkeditor erneut prüfen.</p> : <>
          {group.options.map((option, index) => <details className="eng-repair-option" key={option.id} open={index === 0 || option.action === 'restore'}>
            <summary><strong>{option.action === 'restore' ? 'Alte Führung wiederherstellen' : `Neue Führung · Variante ${index + 1}`}</strong><span>{option.comparison?.length ?? group.routes.length} betroffene Routen</span></summary>
            <p>{option.label}</p>
            {option.questions.map(question => <p key={question}>{question}</p>)}
            {!!option.comparison?.length && <div className="eng-repair-comparison"><table><thead><tr><th>Route / Funktionspartner</th><th>Bisherige Führung</th><th>{option.action === 'restore' ? 'Wiederhergestellte Führung' : 'Neue Führung'}</th></tr></thead><tbody>{option.comparison.map(route => <tr key={route.id}><th scope="row">{route.code}<small>{route.functions ? `${route.functions.source.function} → ${route.functions.destinations.map(p => p.function).join(', ')}` : route.name}</small></th><td>{route.before}</td><td>{route.after}</td></tr>)}</tbody></table></div>}
            <button className={`button ${option.action === 'restore' ? 'secondary' : 'primary'}`} type="button" disabled={busy} onClick={() => void choose(group, option)}>{option.action === 'restore' ? 'Alte Führung wiederherstellen' : 'Neue Führung übernehmen'}</button>
          </details>)}
          {group.restore_unavailable && <p className="muted">Wiederherstellung: {group.restore_unavailable}</p>}
          <button className="button secondary" type="button" disabled={busy} onClick={() => setDeferred(old => new Set([...old, group.id]))}>
            Später entscheiden
          </button>
        </>}
      </section>)}
      <footer><button className="button secondary" type="button" disabled={busy} onClick={() => void start()}>Erneut prüfen</button>
        <button className="button secondary" type="button" disabled={busy} onClick={() => dialog.current?.close()}>Schließen</button></footer>
    </dialog>
  </>;
}

"use client";

import { useState } from "react";
import type { EngMessage, EngSignal } from "@/lib/types";
import { simulationScopeFrom, simulationScopeValid, type SimulationScope } from "@/lib/simulation-scope";

export function SimulationScopeSelector({ scope, onChange, messages, signals, disabled = false }: {
  scope: SimulationScope;
  onChange: (scope: SimulationScope) => void;
  messages: EngMessage[];
  signals: EngSignal[];
  disabled?: boolean;
}) {
  const [search, setSearch] = useState("");
  const query = search.trim().toLocaleLowerCase();
  const active = (row: EngMessage | EngSignal) => !["REJECTED", "SUPERSEDED", "DEPRECATED", "OUTDATED"].includes(String(row.lifecycle_state ?? "").toUpperCase());
  const activeMessages = messages.filter(active);
  const activeSignals = signals.filter(active);
  const filter = (row: EngMessage | EngSignal) => !query || [row.name, row.id].some((value) => String(value).toLocaleLowerCase().includes(query));
  const rows = scope.mode === "SIGNAL" ? activeSignals.filter(filter) : activeMessages.filter(filter);
  const key = scope.mode === "SIGNAL" ? "signal_ids" : "message_ids";
  const selected = new Set(scope[key]);
  function changeMode(mode: SimulationScope["mode"]) {
    onChange(simulationScopeFrom({ mode, include_all: mode === "ALL", message_ids: [], signal_ids: [], reason: scope.reason }));
  }
  function toggle(id: string, checked: boolean) {
    const next = new Set(selected);
    if (checked) next.add(id); else next.delete(id);
    onChange({ ...scope, [key]: [...next].sort() });
  }
  return <section className="panel simulation-scope-panel">
    <div className="compact-heading"><div><p className="eyebrow">Simulationsumfang</p><h2>Was soll geprüft und simuliert werden?</h2></div></div>
    <p>Diese Auswahl gilt gemeinsam für Routing-Prüfung, Preflight und Simulation. Jede benötigte Nachricht und jedes benötigte Signal braucht eine bestätigte Transportroute.</p>
    <div className="simulation-scope-toolbar" role="group" aria-label="Simulationsumfang">
      {(["ALL", "MESSAGE", "SIGNAL"] as const).map((mode) => <button aria-pressed={scope.mode === mode} className={scope.mode === mode ? "active" : ""} disabled={disabled} key={mode} onClick={() => changeMode(mode)} type="button">{{ ALL: "Gesamtes Modell", MESSAGE: "Nachrichten auswählen", SIGNAL: "Signale auswählen" }[mode]}</button>)}
      {scope.mode !== "ALL" && <input aria-label="Nachrichten und Signale suchen" onChange={(event) => setSearch(event.target.value)} placeholder="Name oder ID suchen" value={search} />}
    </div>
    {scope.mode === "ALL" ? <div className="simulation-scope-summary"><strong>{activeMessages.length} aktive Nachrichten und {activeSignals.length} aktive Signale</strong><span>Fehlende Routen werden als Lücke gemeldet. Der Umfang wird nicht automatisch auf vorhandene Routen verkleinert.</span></div> : <>
      <label><span>Begründung für den eingeschränkten Umfang</span><input aria-required="true" disabled={disabled} value={scope.reason} onChange={(event) => onChange({ ...scope, reason: event.target.value })} placeholder="Warum bleiben die übrigen Modellobjekte außerhalb dieses Laufs?" /></label>
      {!simulationScopeValid(scope) && <p role="status">Zum Prüfen mindestens ein Objekt auswählen und die Einschränkung begründen.</p>}
      {scope.mode === "SELECTED" && <p>Gespeicherte kombinierte Auswahl: {scope.message_ids.length} Nachrichten und {scope.signal_ids.length} Signale. Für eine neue Auswahl einen Modus wählen.</p>}
      <p>{scope.message_ids.length} Nachrichten und {scope.signal_ids.length} Signale ausgewählt. Bei Nachrichten werden alle enthaltenen Signale mitgeprüft.</p>
      {scope.mode !== "SELECTED" && <div className="simulation-scope-list">{rows.map((row) => <label className={selected.has(row.id) ? "selected" : ""} key={row.id}><input checked={selected.has(row.id)} disabled={disabled} onChange={(event) => toggle(row.id, event.target.checked)} type="checkbox" /><span>{row.name}</span><small>{row.id}</small></label>)}{!rows.length && <p>Keine passenden Objekte.</p>}</div>}
    </>}
  </section>;
}

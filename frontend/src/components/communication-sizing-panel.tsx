"use client";

import { useState } from "react";
import { dimensionCommunications, applyCommunicationSizing, type CommunicationSizingPlan } from "@/lib/workflow-api";
import { notifyWorkflowChanged } from "./workflow-header";

const percent = (value?: number) => value == null ? "—" : `${value.toFixed(2)} %`;

export function CommunicationSizingPanel() {
  const [plan, setPlan] = useState<CommunicationSizingPlan | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [minimum, setMinimum] = useState("20");
  const [maximum, setMaximum] = useState("50");
  const [target, setTarget] = useState("60");
  const [slotLimit, setSlotLimit] = useState("90");
  const [edited, setEdited] = useState(false);

  async function calculate() {
    setBusy(true); setMessage(""); setPlan(null);
    try {
      // First load uses the actual saved policy; editable values only override
      // the fields the user can see, preserving bus timing and candidate lists.
      const saved = await dimensionCommunications();
      const result = edited ? await dimensionCommunications({...saved.policy, enabled: true,
        minimum_interval_ms: Number(minimum), maximum_generated_period_ms: Number(maximum),
        target_load_percent: Number(target), maximum_slot_load_percent: Number(slotLimit)}) : saved;
      setPlan(result); setEdited(false);
      setMinimum(String(result.policy.minimum_interval_ms)); setMaximum(String(result.policy.maximum_generated_period_ms));
      setTarget(String(result.policy.target_load_percent)); setSlotLimit(String(result.policy.maximum_slot_load_percent));
    } catch (error) { setMessage(error instanceof Error ? error.message : "Dimensionierung fehlgeschlagen."); }
    finally { setBusy(false); }
  }

  async function apply() {
    if (!plan) return;
    setBusy(true); setMessage("");
    try {
      const receipt = await applyCommunicationSizing(plan);
      setMessage(`${receipt.changed_messages} Nachrichten und ${receipt.changed_routes} Routen übernommen. ${receipt.valid_routes} Routen erneut geprüft und freigegeben.${receipt.invalid_routes.length ? ` ${receipt.invalid_routes.length} Routen benötigen eine Korrektur.` : ""}`);
      setPlan(null); notifyWorkflowChanged();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Übernahme fehlgeschlagen."); }
    finally { setBusy(false); }
  }

  function edit(set: (v: string) => void, value: string) { set(value); setEdited(true); setPlan(null); }

  return <details className="panel communication-sizing-panel">
    <summary><strong>Kommunikation automatisch dimensionieren</strong></summary>
    <p>Der Simulator prüft Zyklusvarianten für jeden Bus und plant LIN-Sendeplätze beziehungsweise CAN-Antwortgrenzen. Bestätigte Fristen, Datenalter und gesperrte Zyklen bleiben verbindlich.</p>
    <div className="analysis-scenario-row">
      <label>Mindest-Sendeabstand (ms)<input type="number" min="1" disabled={busy} value={minimum} onChange={e => edit(setMinimum, e.target.value)} /></label>
      <label>Maximaler generierter Zyklus (ms)<input type="number" min="1" disabled={busy} value={maximum} onChange={e => edit(setMaximum, e.target.value)} /></label>
      <label>Ziel-Buslast (%)<input type="number" min="1" max="100" disabled={busy} value={target} onChange={e => edit(setTarget, e.target.value)} /></label>
      <label>Maximale LIN-Slotbelegung (%)<input type="number" min="1" max="100" disabled={busy} value={slotLimit} onChange={e => edit(setSlotLimit, e.target.value)} /></label>
    </div>
    <button type="button" className="button primary" disabled={busy} onClick={() => void calculate()}>{busy ? "Prüft …" : "Zyklen und Sendeplan ermitteln"}</button>
    {message && <p role="status">{message}</p>}
    {plan && <>
      <p><strong>{plan.changes.length} Nachrichtenänderungen</strong> · {plan.history_matches.length} passende Erfahrungen aus früheren Dimensionierungen. Jede Variante wurde mit den aktuellen Anforderungen neu geprüft.</p>
      {plan.status === "PARTIAL" && <p className="notice warning">Einige Netze benötigen weitere Maßnahmen. Die bestätigte Mindestabstandsregel kann übernommen werden. Änderungen ohne vollständigen Zeitnachweis sind gesondert gekennzeichnet.</p>}
      <div style={{maxHeight: 520, overflow: "auto"}}>
        {plan.networks.map(network => <details key={network.network_id} style={{padding: "12px 0", borderBottom: "1px solid var(--border, #293746)"}}>
          <summary><strong>{network.network_name}</strong> · {network.protocol} · Zyklen: {network.effective_periods_ms?.join(" / ") || "offen"} ms · {percent(network.schedule?.nominal_load_percent)}</summary>
          <p>{network.explanation}</p>
          {network.schedule?.slot_load_percent != null && <p>Reservierte LIN-Sendeplätze: {percent(network.schedule.slot_load_percent)}</p>}
          <table className="eng-table"><thead><tr><th>Zyklus-Untergrenze</th><th>Busbedarf</th><th>LIN-Slots</th><th>Bewertung</th></tr></thead><tbody>
            {network.attempts.map(attempt => <tr key={attempt.floor_ms}><td>{attempt.floor_ms} ms</td><td>{percent(attempt.load_percent)}</td><td>{percent(attempt.slot_load_percent)}</td><td>{attempt.fits ? "Geeignet unter den Modellannahmen" : attempt.reasons.join(" · ") || "Weiterer Nachweis erforderlich"}</td></tr>)}
          </tbody></table>
          {network.schedule?.assumptions && <p>Prüfannahmen: {network.schedule.assumptions.join("; ")}.</p>}
        </details>)}
      </div>
      {plan.changes.length > 0 && <>
        <details><summary>Nachrichtenänderungen prüfen</summary><ul>{plan.changes.map(change => <li key={change.message_id}>{change.name}: {change.before_ms} → {change.after_ms} ms{change.evaluation === "POLICY_ONLY_UNVERIFIED" ? " · Mindestabstandsregel; Ethernet-Zeitnachweis offen" : ""}</li>)}</ul></details>
        <p>Die Übernahme aktualisiert Nachrichten, Signale, Routing und Sendeplan gemeinsam. Nachgelagerte Ergebnisse werden zur Neuberechnung markiert.</p>
        <button type="button" className="button primary" disabled={busy || edited} onClick={() => void apply()}>Übernehmen und valide Routen freigeben</button>
      </>}
    </>}
  </details>;
}

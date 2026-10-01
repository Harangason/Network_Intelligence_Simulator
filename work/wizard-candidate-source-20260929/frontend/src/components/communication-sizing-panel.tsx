"use client";

import { useEffect, useState } from "react";
import { dimensionCommunications, applyCommunicationSizing, type CommunicationSizingPlan } from "@/lib/workflow-api";
import { notifyWorkflowChanged } from "./workflow-header";
import { readActiveProjectId, SETTINGS_EVENT } from "@/lib/user-settings";

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
  const [projectId, setProjectId] = useState("");

  useEffect(() => {
    const syncProject = () => {
      const next = readActiveProjectId();
      setProjectId(current => current === next ? current : next);
      setPlan(null);
      setMessage("");
      setEdited(false);
    };
    syncProject();
    window.addEventListener(SETTINGS_EVENT, syncProject);
    window.addEventListener("popstate", syncProject);
    return () => {
      window.removeEventListener(SETTINGS_EVENT, syncProject);
      window.removeEventListener("popstate", syncProject);
    };
  }, []);

  async function calculate() {
    setBusy(true); setMessage(""); setPlan(null);
    try {
      // First load uses the actual saved policy; editable values only override
      // the fields the user can see, preserving bus timing and candidate lists.
      const activeProject = readActiveProjectId();
      setProjectId(activeProject);
      const saved = await dimensionCommunications(undefined, activeProject);
      const result = edited ? await dimensionCommunications({...saved.policy, enabled: true,
        minimum_interval_ms: Number(minimum), maximum_generated_period_ms: Number(maximum),
        target_load_percent: Number(target), maximum_slot_load_percent: Number(slotLimit)}, activeProject) : saved;
      if (readActiveProjectId() !== activeProject) return;
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
      const activeProject = readActiveProjectId();
      if (activeProject !== projectId) throw new Error("Das aktive Projekt wurde geändert. Bitte neu berechnen.");
      const receipt = await applyCommunicationSizing(plan, activeProject);
      setMessage(`${receipt.changed_messages} Nachrichten und ${receipt.changed_routes} Routen übernommen. ${receipt.valid_routes} Routen erneut geprüft und freigegeben.${receipt.invalid_routes.length ? ` ${receipt.invalid_routes.length} Routen benötigen eine Korrektur.` : ""}`);
      setPlan(null); notifyWorkflowChanged();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Übernahme fehlgeschlagen."); }
    finally { setBusy(false); }
  }

  function edit(set: (v: string) => void, value: string) { set(value); setEdited(true); setPlan(null); }

  const protocols = Object.keys(plan?.protocol_inventory ?? {}).sort();
  const canDimension = plan?.networks.some(network => network.status === "FEASIBLE_UNDER_ASSUMPTIONS" && network.protocol !== "I2C") ?? false;
  const hasI2c = protocols.includes("I2C") || plan?.networks.some(network => network.protocol === "I2C") === true;
  const hasCanOrLin = protocols.some(protocol => ["CAN", "CAN_CLASSIC", "CAN_FD", "CANFD", "LIN"].includes(protocol));

  return <details className="panel communication-sizing-panel">
    <summary><strong>Kommunikation automatisch dimensionieren</strong></summary>
    <p>{protocols.length ? `Erkannte Technologien in ${projectId}: ${protocols.join(", ")}.` : "Die Dimensionierung verwendet ausschließlich die physischen Verbindungen und Anforderungen des aktiven Projekts."} Bestätigte Fristen, Datenalter und gesperrte Zyklen bleiben verbindlich. Die Planung vergleicht alle zulässigen Zyklusvarianten und ändert weder Technologieparameter noch Frame-Kodierungen.</p>
    {hasI2c && <p className="notice warning">I2C ist im Projekt vorhanden. Der Zeitnachweis bleibt offen, bis Master, Slave-Adresse, Clock-Stretching-Grenze und Transferumfang modelliert sind. LIN-Slots und CAN-Arbitrierung werden dafür nicht angesetzt.</p>}
    <div className="analysis-scenario-row">
      <label>Mindest-Sendeabstand (ms)<input type="number" min="1" disabled={busy} value={minimum} onChange={e => edit(setMinimum, e.target.value)} /></label>
      <label>Maximaler generierter Zyklus (ms)<input type="number" min="1" disabled={busy} value={maximum} onChange={e => edit(setMaximum, e.target.value)} /></label>
      {hasCanOrLin && <label>Ziel-Buslast (%)<input type="number" min="1" max="100" disabled={busy} value={target} onChange={e => edit(setTarget, e.target.value)} /></label>}
      {protocols.includes("LIN") && <label>Maximale LIN-Slotbelegung (%)<input type="number" min="1" max="100" disabled={busy} value={slotLimit} onChange={e => edit(setSlotLimit, e.target.value)} /></label>}
    </div>
    <button type="button" className="button primary" disabled={busy} onClick={() => void calculate()}>{busy ? "Prüft …" : "Zyklusvarianten für dieses Projekt prüfen"}</button>
    {message && <p role="status">{message}</p>}
    {plan && <>
      <p><strong>{plan.changes.length} Nachrichtenänderungen</strong> · {plan.history_matches.length} passende Erfahrungen aus früheren Dimensionierungen. Alle zulässigen Varianten werden mit den aktuellen Anforderungen verglichen; Linkrate, Technologie, Payload und Kodierung bleiben fest.</p>
      {plan.status === "PARTIAL" && <p className="notice warning">Einige Netze benötigen weitere Maßnahmen. Änderungen werden nur für vollständig geprüfte Netze angeboten; offene Zeitnachweise bleiben unverändert.</p>}
      <div style={{maxHeight: 520, overflow: "auto"}}>
        {plan.networks.map(network => <details key={network.network_id} style={{padding: "12px 0", borderBottom: "1px solid var(--border, #293746)"}}>
          <summary><strong>{network.network_name}</strong> · {network.protocol} · Zyklen: {network.effective_periods_ms?.join(" / ") || "offen"} ms · {percent(network.schedule?.nominal_load_percent)}</summary>
          <p>{network.explanation}</p>
          {network.schedule?.hardware_review_proposal && <div className="notice warning">
            <p><strong>Hardwareprofil-Vorschlag zur Prüfung</strong> · {network.schedule.hardware_review_proposal.source}. Geräteprofil und Zeitfreigabe sind noch nicht bestätigt.</p>
            {network.schedule.hardware_review_proposal.endpoint_candidates.length > 0 && <p>Mögliche Endpunkte: {network.schedule.hardware_review_proposal.endpoint_candidates.join(", ")}. Master und Gerätezuordnung fachlich bestätigen.</p>}
            <ul>{network.schedule.hardware_review_proposal.fields.map(field => <li key={field.key}>{field.label}: {field.value ?? "offen"}{field.candidate != null ? ` · Profilkandidat ${field.candidate.toLocaleString("de-DE")} (ungeprüft)` : ""}{field.state === "CONFLICT" ? " · widersprüchliche Angaben" : ""}</li>)}</ul>
            <p>Die Werte am jeweiligen Hardware Interface bestätigen. Bis dahin bleibt der Reaktionszeitnachweis gesperrt.</p>
          </div>}
          {network.protocol === "LIN" && network.schedule?.slot_load_percent != null && <p>Reservierte LIN-Sendeplätze: {percent(network.schedule.slot_load_percent)}</p>}
          <table className="eng-table"><thead><tr><th>Zyklus-Untergrenze</th><th>Busbedarf</th>{network.protocol === "LIN" && <th>LIN-Slots</th>}<th>Bewertung</th></tr></thead><tbody>
            {network.attempts.map(attempt => <tr key={attempt.floor_ms}><td>{attempt.floor_ms} ms</td><td>{percent(attempt.load_percent)}</td>{network.protocol === "LIN" && <td>{percent(attempt.slot_load_percent)}</td>}<td>{attempt.fits ? "Geeignet unter den Modellannahmen" : attempt.reasons.join(" · ") || "Weiterer Nachweis erforderlich"}</td></tr>)}
          </tbody></table>
          {network.schedule?.assumptions && <p>Prüfannahmen: {network.schedule.assumptions.join("; ")}.</p>}
        </details>)}
      </div>
      {plan.changes.length > 0 && canDimension && <>
        <details><summary>Nachrichtenänderungen prüfen</summary><ul>{plan.changes.map(change => <li key={change.message_id}>{change.name}: {change.before_ms} → {change.after_ms} ms{change.evaluation === "POLICY_ONLY_UNVERIFIED" ? " · Mindestabstandsregel; Ethernet-Zeitnachweis offen" : ""}</li>)}</ul></details>
        <p>Die Übernahme aktualisiert Nachrichten, Signale, Routing und Sendeplan gemeinsam. Nachgelagerte Ergebnisse werden zur Neuberechnung markiert.</p>
        <button type="button" className="button primary" disabled={busy || edited || readActiveProjectId() !== projectId} onClick={() => void apply()}>Geprüfte Änderungen übernehmen</button>
      </>}
    </>}
  </details>;
}

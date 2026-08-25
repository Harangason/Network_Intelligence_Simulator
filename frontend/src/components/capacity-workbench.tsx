"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  calculateCapacity,
  calculateCapacityScenario,
  getCapacity,
  getWorkflow,
  optimizeCapacity,
  saveWorkflowParameters,
  setWorkflowContext,
  type AnalysisFinding,
  type CapacityImpact,
  type CapacityNetwork,
  type CapacityResults,
  type WorkflowStatus,
} from "@/lib/workflow-api";
import { notifyWorkflowChanged } from "./workflow-header";

type View = "overview" | "networks" | "messages" | "routes" | "timing" | "gateways" | "critical" | "recommendations";

export function CapacityWorkbench() {
  const [results, setResults] = useState<CapacityResults | null>(null);
  const [findings, setFindings] = useState<AnalysisFinding[]>([]);
  const [status, setStatus] = useState<WorkflowStatus | null>(null);
  const [outdated, setOutdated] = useState(false);
  const [outdatedReason, setOutdatedReason] = useState("");
  const [view, setView] = useState<View>("overview");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [scenarioBitrate, setScenarioBitrate] = useState("");
  const [scenarioBurst, setScenarioBurst] = useState("1.25");
  const [scenarioQueuePolicy, setScenarioQueuePolicy] = useState("FIFO");
  const [scenario, setScenario] = useState<CapacityResults | null>(null);
  const [scenarioImpact, setScenarioImpact] = useState<CapacityImpact | null>(null);
  const [scenarioOverrides, setScenarioOverrides] = useState<Record<string, unknown>>({});
  const [proposals, setProposals] = useState<Array<Record<string, unknown>>>([]);
  const [selectedNetworkId, setSelectedNetworkId] = useState<string | null>(null);
  const [networkSort, setNetworkSort] = useState<"burst" | "reserve" | "latency">("burst");

  useEffect(() => {
    void setWorkflowContext({ selected_network: selectedNetworkId }).catch(() => undefined);
  }, [selectedNetworkId]);

  useEffect(() => {
    getCapacity()
      .then((snapshot) => {
        setResults(snapshot.results as CapacityResults);
        setFindings(snapshot.findings);
        setStatus(snapshot.status);
        setOutdated(snapshot.is_outdated);
        setOutdatedReason(snapshot.outdated_reason ?? "");
      })
      .catch(() => undefined);
  }, []);

  async function calculate() {
    setBusy(true);
    setError("");
    try {
      const response = await calculateCapacity();
      setResults(response.results);
      setFindings(response.findings);
      setStatus(response.status);
      setOutdated(false);
      setScenario(null);
      setScenarioImpact(null);
      notifyWorkflowChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Berechnung fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  async function runScenario() {
    setBusy(true);
    setError("");
    try {
      const overrides: Record<string, unknown> = { burst_factor: Number(scenarioBurst), queue_policy: scenarioQueuePolicy };
      if (scenarioBitrate) overrides.bitrate = Number(scenarioBitrate);
      const response = await calculateCapacityScenario(overrides);
      setScenario(response.results);
      setScenarioImpact(response.impact ?? null);
      setScenarioOverrides(overrides);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Szenario konnte nicht berechnet werden.");
    } finally {
      setBusy(false);
    }
  }

  async function applyScenario() {
    setBusy(true);
    setError("");
    try {
      const workflow = await getWorkflow();
      await saveWorkflowParameters({ ...workflow.parameters, ...scenarioOverrides });
      setScenario(null);
      setScenarioImpact(null);
      await calculate();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Szenario konnte nicht in den Draft übernommen werden.");
    } finally {
      setBusy(false);
    }
  }

  async function requestOptimization() {
    setBusy(true);
    setError("");
    try {
      setProposals((await optimizeCapacity()).proposals);
      setView("recommendations");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Optimierungsvorschläge sind nicht verfügbar.");
    } finally {
      setBusy(false);
    }
  }

  const shown = scenario ?? results;
  const critical = useMemo(
    () => shown?.routes.filter((route) => route.status !== "NORMAL") ?? [],
    [shown],
  );
  const sortedNetworks = useMemo(() => [...(shown?.networks ?? [])].sort((left, right) => {
    if (networkSort === "reserve") return left.capacity_reserve_percent - right.capacity_reserve_percent;
    if (networkSort === "latency") return right.worst_end_to_end_latency_ms - left.worst_end_to_end_latency_ms;
    return right.burst_load_percent - left.burst_load_percent;
  }), [networkSort, shown]);
  const selectedNetwork = shown?.networks.find((item) => item.network_id === selectedNetworkId) ?? null;

  return (
    <section className="analysis-workbench">
      <div className="analysis-toolbar">
        <div>
          <p className="eyebrow">Engineering calculation</p>
          <h2>Capacity & Timing</h2>
          <p>Technologiespezifische Last-, Reserve-, Latenz-, Jitter- und Queueing-Abschätzung.</p>
        </div>
        <div className="analysis-actions">
          <button className="button secondary" disabled={busy} onClick={() => void runScenario()} type="button">
            Szenario berechnen
          </button>
          <button className="button secondary" disabled={busy} onClick={() => void requestOptimization()} type="button">KI-Vorschläge</button>
          <button className="button primary" disabled={busy} onClick={() => void calculate()} type="button">
            {busy ? "Berechnet …" : "Aktuell berechnen"}
          </button>
        </div>
      </div>

      {outdated && (
        <div className="workflow-blocker warning">
          <strong>Analyse ist OUTDATED</strong>
          <span>{outdatedReason || "Eine vorgelagerte Quelle wurde geändert."}</span>
        </div>
      )}
      {scenario && <div className="workflow-blocker info"><strong>What-if-Szenario</strong><span>Nur Vergleich, Quelldaten bleiben unverändert.</span><button className="button primary tiny" disabled={busy} onClick={() => void applyScenario()} type="button">Auf Draft anwenden</button></div>}
      {error && <div className="notice error">{error}</div>}

      <div className="analysis-scenario-row">
        <label>
          <span>Alternative Bitrate (bit/s)</span>
          <input inputMode="numeric" onChange={(event) => setScenarioBitrate(event.target.value)} placeholder="aktuellen Wert verwenden" value={scenarioBitrate} />
        </label>
        <label>
          <span>Burst-Faktor</span>
          <input min="1" onChange={(event) => setScenarioBurst(event.target.value)} step="0.05" type="number" value={scenarioBurst} />
        </label>
        <label><span>Queue Policy</span><select onChange={(event) => setScenarioQueuePolicy(event.target.value)} value={scenarioQueuePolicy}><option>FIFO</option><option>STRICT_PRIORITY</option><option>WRR</option><option>TAS</option><option>CBS</option></select></label>
        {scenario && <button className="text-command" onClick={() => setScenario(null)} type="button">Vergleich schließen</button>}
      </div>

      {scenarioImpact && <div className="impact-strip"><Metric label="Δ Peak" value={`${scenarioImpact.delta.peak_load_percent.toFixed(2)} %`} /><Metric label="Δ Burst" value={`${scenarioImpact.delta.burst_load_percent.toFixed(2)} %`} /><Metric label="Δ Reserve" value={`${scenarioImpact.delta.capacity_reserve_percent.toFixed(2)} %`} /><Metric label="Δ E2E" value={`${scenarioImpact.delta.end_to_end_latency_ms.toFixed(3)} ms`} /></div>}

      {shown ? (
        <>
          <div className="metric-strip">
            <Metric label="Peak Load" value={`${shown.overview.max_peak_load_percent.toFixed(2)} %`} />
            <Metric label="Kapazitätsreserve" value={`${shown.overview.minimum_capacity_reserve_percent.toFixed(2)} %`} />
            <Metric label="Worst E2E" value={`${shown.overview.worst_end_to_end_latency_ms.toFixed(3)} ms`} />
            <Metric label="Netze / Routen" value={`${shown.overview.network_count} / ${shown.overview.route_count}`} />
            <Metric label="Status" value={status ?? shown.overview.status} tone={status ?? shown.overview.status} />
          </div>

          <div className="analysis-tabs" role="tablist" aria-label="Capacity-Ansichten">
            {(["overview", "networks", "messages", "routes", "timing", "gateways", "critical", "recommendations"] as View[]).map((item) => (
              <button className={view === item ? "active" : ""} key={item} onClick={() => setView(item)} role="tab" type="button">
                {({ overview: "Übersicht", networks: "Netze", messages: "Messages", routes: "Routen", timing: "Timing & Sync", gateways: "Gateways", critical: "Kritisch", recommendations: "Empfehlungen" } as Record<View, string>)[item]}
              </button>
            ))}
          </div>

          {(view === "overview" || view === "networks") && <>
            <div className="analysis-sort-row"><span>Sortierung</span><select onChange={(event) => setNetworkSort(event.target.value as typeof networkSort)} value={networkSort}><option value="burst">Burst Load</option><option value="reserve">Geringste Reserve</option><option value="latency">Worst E2E</option></select></div>
            <NetworkTable items={sortedNetworks} onSelect={setSelectedNetworkId} selectedId={selectedNetworkId} />
            {selectedNetwork && <NetworkDetail network={selectedNetwork} routes={shown.routes.filter((route) => route.network_id === selectedNetwork.network_id)} />}
          </>}
          {view === "messages" && <MessageTable items={shown.messages} />}
          {view === "routes" && <RouteTable items={shown.routes} />}
          {view === "timing" && <TimingAnalysis results={shown} />}
          {view === "critical" && <RouteTable items={critical} />}
          {view === "gateways" && (
            <div className="analysis-list">
              {shown.gateways.length ? shown.gateways.map((gateway, index) => (
                <div key={String(gateway.gateway_id ?? index)}><strong>{String(gateway.name ?? gateway.gateway_id)}</strong><span>{String(gateway.route_count ?? 0)} Routen · {String(gateway.processing_delay_ms ?? 0)} ms Verarbeitung</span></div>
              )) : <EmptyAnalysis text="Keine Gateway-Hops in den aktuellen Routen." />}
            </div>
          )}
          {view === "recommendations" && (
            <div className="analysis-list findings-list">
              {proposals.map((proposal) => <div className="finding finding-info" key={String(proposal.id)}><span>AI PROPOSAL</span><strong>{String(proposal.summary)}</strong><small>{String(proposal.kind)} · nicht angewendet</small></div>)}
              {findings.length ? findings.map((finding, index) => (
                <div className={`finding finding-${finding.severity.toLowerCase()}`} key={`${finding.code}-${index}`}>
                  <span>{finding.severity}</span><strong>{finding.message}</strong><small>{finding.recommendation ?? "Keine Aktion erforderlich."}</small>
                </div>
              )) : <EmptyAnalysis text="Keine Kapazitätsauffälligkeiten gefunden." />}
            </div>
          )}
        </>
      ) : (
        <EmptyAnalysis text="Noch keine Analyse vorhanden. Starte die erste belastbare Berechnung." />
      )}

      <div className="analysis-footer-actions">
        <Link className="button secondary" href="/studio?mode=parameters">Parameter öffnen</Link>
        <Link className="button primary" href="/studio/validation">Weiter zum Preflight →</Link>
      </div>
    </section>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return <div className={tone ? `metric metric-${tone.toLowerCase()}` : "metric"}><span>{label}</span><strong>{value}</strong></div>;
}

function NetworkTable({ items, onSelect, selectedId }: { items: CapacityResults["networks"]; onSelect: (id: string) => void; selectedId: string | null }) {
  if (!items.length) return <EmptyAnalysis text="Keine Netze mit zugeordneten Routen vorhanden." />;
  return (
    <div className="analysis-table-wrap"><table className="analysis-table"><thead><tr><th>Netz</th><th>Technologie</th><th>Ø Load</th><th>Peak</th><th>Reserve</th><th>Worst E2E</th><th>Status</th></tr></thead><tbody>
      {items.map((item) => <tr className={selectedId === item.network_id ? "selected" : ""} key={item.network_id} onClick={() => onSelect(item.network_id)}><td><strong>{item.network_id}</strong></td><td>{item.protocol}</td><td>{item.average_load_percent.toFixed(2)} %</td><td>{item.peak_load_percent.toFixed(2)} %</td><td>{item.capacity_reserve_percent.toFixed(2)} %</td><td>{item.worst_end_to_end_latency_ms.toFixed(3)} ms</td><td><span className={`load-status load-${item.status.toLowerCase()}`}>{item.status}</span></td></tr>)}
    </tbody></table></div>
  );
}

function NetworkDetail({ network, routes }: { network: CapacityNetwork; routes: CapacityResults["routes"] }) {
  return (
    <section className="network-capacity-detail">
      <div><p className="eyebrow">Network drilldown</p><h3>{network.network_id}</h3><span>{network.protocol} · {network.bitrate ? `${network.bitrate.toLocaleString("de-DE")} bit/s` : "historischer Snapshot"}</span></div>
      <dl className="overview-list"><div><dt>Burst</dt><dd>{network.burst_load_percent.toFixed(2)} %</dd></div><div><dt>Margin</dt><dd>{(network.capacity_margin_percent ?? 100 - network.burst_load_percent).toFixed(2)} %</dd></div><div><dt>Routen</dt><dd>{routes.length}</dd></div></dl>
      <div className="capacity-contributors"><strong>Top Contributors</strong>{(network.top_contributors ?? routes.slice(0, 5).map((route) => ({ route_id: route.route_id, name: route.name, load_percent: route.average_load_percent }))).map((item) => <span key={item.route_id}>{item.name}<b>{item.load_percent.toFixed(2)} %</b></span>)}</div>
      <RouteTable items={routes} />
    </section>
  );
}

function RouteTable({ items }: { items: CapacityResults["routes"] }) {
  if (!items.length) return <EmptyAnalysis text="Keine passenden Routen vorhanden." />;
  return (
    <div className="analysis-table-wrap"><table className="analysis-table"><thead><tr><th>Route</th><th>Netz</th><th>Payload / Cycle</th><th>Peak</th><th>E2E</th><th>Modell</th></tr></thead><tbody>
      {items.map((item) => <tr key={item.route_id}><td><strong>{item.name}</strong><small>{item.route_code}</small></td><td>{item.network_id}</td><td>{item.payload_bytes} B / {item.cycle_ms} ms</td><td>{item.peak_load_percent.toFixed(2)} %</td><td>{item.end_to_end_latency_ms.toFixed(3)} ms</td><td><code>{item.calculation_model}</code></td></tr>)}
    </tbody></table></div>
  );
}

function MessageTable({ items }: { items: CapacityResults["messages"] }) {
  if (!items.length) return <EmptyAnalysis text="Keine Messages mit Timingdaten vorhanden." />;
  return (
    <div className="analysis-table-wrap"><table className="analysis-table"><thead><tr><th>Message</th><th>Netz</th><th>Technologie</th><th>Payload / Cycle</th><th>Ø Load</th><th>Peak</th><th>Modell</th></tr></thead><tbody>
      {items.map((item, index) => <tr key={String(item.message_id ?? index)}><td><strong>{String(item.name ?? item.message_id)}</strong></td><td>{String(item.network_id ?? "—")}</td><td>{String(item.protocol ?? "—")}</td><td>{String(item.payload_bytes ?? "—")} B / {String(item.cycle_ms ?? "—")} ms</td><td>{Number(item.average_load_percent ?? 0).toFixed(2)} %</td><td>{Number(item.peak_load_percent ?? 0).toFixed(2)} %</td><td><code>{String(item.calculation_model ?? "—")}</code></td></tr>)}
    </tbody></table></div>
  );
}

function TimingAnalysis({ results }: { results: CapacityResults }) {
  const timing = results.timing;
  const reliability = results.reliability;
  const synchronization = results.synchronization;
  const worstQueue = timing?.worst_queueing_latency_ms
    ?? Math.max(0, ...results.routes.map((route) => route.queueing_latency_ms));
  const worstJitter = timing?.worst_estimated_jitter_ms
    ?? Math.max(0, ...results.routes.map((route) => route.estimated_jitter_ms ?? 0));

  return (
    <div className="timing-analysis">
      <div className="metric-strip compact">
        <Metric label="Worst Queueing" value={`${worstQueue.toFixed(3)} ms`} />
        <Metric label="Worst Jitter" value={`${worstJitter.toFixed(3)} ms`} />
        <Metric label="Queue Policy" value={timing?.queue_policy ?? "FIFO"} />
        <Metric label="Retransmission" value={`${((reliability?.configured_retransmission_rate ?? 0) * 100).toFixed(2)} %`} />
        <Metric label="Clock Drift" value={`${synchronization?.clock_drift_ppm ?? 0} ppm`} />
        <Metric label="Sync Precision" value={`${synchronization?.sync_precision_ms ?? 0} ms`} />
      </div>
      <div className="analysis-table-wrap"><table className="analysis-table"><thead><tr><th>Route</th><th>Transmission</th><th>Queueing</th><th>Gateway</th><th>E2E</th><th>Jitter / Budget</th><th>Deadline</th></tr></thead><tbody>
        {results.routes.map((route) => <tr key={route.route_id}><td><strong>{route.name}</strong><small>{route.route_code}</small></td><td>{(route.transmission_latency_ms ?? 0).toFixed(3)} ms</td><td>{route.queueing_latency_ms.toFixed(3)} ms</td><td>{(route.gateway_latency_ms ?? 0).toFixed(3)} ms</td><td>{route.end_to_end_latency_ms.toFixed(3)} ms</td><td>{(route.estimated_jitter_ms ?? 0).toFixed(3)} / {route.jitter_budget_ms ? `${route.jitter_budget_ms.toFixed(3)} ms` : "—"}</td><td>{route.max_latency_ms ? `${route.max_latency_ms} ms` : "—"}</td></tr>)}
      </tbody></table></div>
      {synchronization && (
        <p className="analysis-footnote">Maximale Drift im Beobachtungsfenster: <strong>{synchronization.max_drift_over_observation_ms.toFixed(3)} ms</strong> bei {synchronization.observation_s} s.</p>
      )}
    </div>
  );
}

function EmptyAnalysis({ text }: { text: string }) {
  return <div className="analysis-empty"><strong>Noch keine auswertbaren Daten</strong><p>{text}</p></div>;
}

"use client";

import Link from "next/link";
import { CommunicationSizingPanel } from "./communication-sizing-panel";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  calculateCapacity,
  calculateCapacityScenario,
  getCapacity,
  getCapacityInspectionSources,
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
import { useWorkflowRefresh } from "@/lib/use-workflow-refresh";
import { paginateCapacityItems } from "@/lib/capacity-pagination";
import { buildNetworkInspection, type NetworkInspection } from "@/lib/capacity-network-inspection";
import { readActiveProjectId, withProjectParam } from "@/lib/user-settings";

type View = "overview" | "networks" | "messages" | "routes" | "timing" | "gateways" | "critical" | "recommendations";
type ViewWarningInfo = Record<View, { count: number; reasons: string[] }>;

const CAPACITY_VIEW_LABELS: Record<View, string> = {
  overview: "Übersicht",
  networks: "Netze",
  messages: "Messages",
  routes: "Routen",
  timing: "Timing & Sync",
  gateways: "Gateways",
  critical: "Kritisch",
  recommendations: "Empfehlungen",
};

const CAPACITY_VIEWS: View[] = ["overview", "networks", "messages", "routes", "timing", "gateways", "critical", "recommendations"];

export function CapacityWorkbench({ initialProjectId = "" }: { initialProjectId?: string }) {
  const [results, setResults] = useState<CapacityResults | null>(null);
  const [findings, setFindings] = useState<AnalysisFinding[]>([]);
  const [status, setStatus] = useState<WorkflowStatus | null>(null);
  const [outdated, setOutdated] = useState(false);
  const [outdatedReason, setOutdatedReason] = useState("");
  const [view, setView] = useState<View>("overview");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [scenarioBitrate, setScenarioBitrate] = useState("");
  const [scenarioBurst, setScenarioBurst] = useState("1.5");
  const [scenarioQueuePolicy, setScenarioQueuePolicy] = useState("FIFO");
  const [scenario, setScenario] = useState<CapacityResults | null>(null);
  const [scenarioImpact, setScenarioImpact] = useState<CapacityImpact | null>(null);
  const [scenarioOverrides, setScenarioOverrides] = useState<Record<string, unknown>>({});
  const [proposals, setProposals] = useState<Array<Record<string, unknown>>>([]);
  const [selectedNetworkId, setSelectedNetworkId] = useState<string | null>(null);
  const [networkSort, setNetworkSort] = useState<"burst" | "reserve" | "latency">("burst");
  const [sourceVersions, setSourceVersions] = useState<Record<string, number> | null>(null);

  useEffect(() => {
    void setWorkflowContext({ selected_network: selectedNetworkId }).catch(() => undefined);
  }, [selectedNetworkId]);

  const load = useCallback(async () => {
    try {
      const snapshot = await getCapacity();
      setResults(snapshot.results as CapacityResults);
      setSourceVersions(snapshot.source_versions);
      setFindings(snapshot.findings);
      setStatus(snapshot.status);
      setOutdated(snapshot.is_outdated);
      setOutdatedReason(snapshot.outdated_reason ?? "");
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Capacity-Daten nicht verfügbar.");
    }
  }, []);
  useWorkflowRefresh(load);

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
  const warningInfo = useMemo(
    () => buildCapacityWarningInfo(shown, findings, proposals, status, outdatedReason),
    [findings, outdatedReason, proposals, shown, status],
  );
  const statusDetails = useMemo(
    () => buildStatusDetails(status ?? shown?.overview.status ?? null, warningInfo),
    [shown?.overview.status, status, warningInfo],
  );

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
          <button className="button secondary" disabled={busy} onClick={() => void requestOptimization()} type="button">Zweige optimieren</button>
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
      <CommunicationSizingPanel />

      <div className="analysis-scenario-row">
        <label>
          <span>Alternative Bitrate (bit/s)</span>
          <input inputMode="numeric" onChange={(event) => setScenarioBitrate(event.target.value)} placeholder="aktuellen Wert verwenden" value={scenarioBitrate} />
        </label>
        <label>
          <span>Stress-Faktor für Szenario</span>
          <input min="1" onChange={(event) => setScenarioBurst(event.target.value)} step="0.05" type="number" value={scenarioBurst} />
        </label>
        <label><span>Queue Policy</span><select onChange={(event) => setScenarioQueuePolicy(event.target.value)} value={scenarioQueuePolicy}><option>FIFO</option><option>STRICT_PRIORITY</option><option>WRR</option><option>TAS</option><option>CBS</option></select></label>
        {scenario && <button className="text-command" onClick={() => setScenario(null)} type="button">Vergleich schließen</button>}
      </div>

      {scenarioImpact && <div className="impact-strip"><Metric label="Δ Peak" value={`${scenarioImpact.delta.peak_load_percent.toFixed(2)} %`} /><Metric label="Δ Burst" value={`${scenarioImpact.delta.burst_load_percent.toFixed(2)} %`} /><Metric label="Δ Reserve" value={`${scenarioImpact.delta.capacity_reserve_percent.toFixed(2)} %`} /><Metric label="Δ E2E" value={`${scenarioImpact.delta.end_to_end_latency_ms.toFixed(3)} ms`} /></div>}

      {shown ? (
        <>
          <p>Ø Load beschreibt den nominalen Busbedarf. Peak und Stresslast sind rechnerische Varianten mit Faktor {shown.overview.peak_factor ?? 1.15} und {shown.overview.burst_factor ?? 1.5}; keine gleichzeitig sendenden Teilnehmer und keine Messwerte.</p>
          <div className="metric-strip">
            <Metric label="Peak Load" value={`${shown.overview.max_peak_load_percent.toFixed(2)} %`} />
            <Metric label="Kapazitätsreserve" value={`${shown.overview.minimum_capacity_reserve_percent.toFixed(2)} %`} />
            <Metric label="E2E-Antwortgrenze" value={shown.overview.timing_verified ? `${shown.overview.worst_end_to_end_latency_ms.toFixed(3)} ms` : "Nicht nachgewiesen"} />
            <Metric label="Netze / Routen" value={`${shown.overview.network_count} / ${shown.overview.route_count}`} />
            <Metric details={statusDetails} label="Status" value={status ?? shown.overview.status} tone={status ?? shown.overview.status} />
          </div>

          <div className="analysis-tabs" role="tablist" aria-label="Capacity-Ansichten">
            {CAPACITY_VIEWS.map((item) => {
              const warning = warningInfo[item];
              return (
              <button
                aria-selected={view === item}
                className={`${view === item ? "active" : ""}${warning.count ? " has-warning" : ""}`}
                key={item}
                onClick={() => setView(item)}
                role="tab"
                title={warning.reasons.join("\n")}
                type="button"
              >
                {CAPACITY_VIEW_LABELS[item]}
                {warning.count > 0 && <span aria-label={`${warning.count} Warnungen`} className="tab-warning-indicator">!</span>}
              </button>
            );})}
          </div>
          <CapacityViewWarnings label={CAPACITY_VIEW_LABELS[view]} scenarioActive={Boolean(scenario)} sourceVersions={sourceVersions} warning={warningInfo[view]} />

          {(view === "overview" || view === "networks") && <>
            <div className="analysis-sort-row"><label htmlFor="capacity-network-sort">Sortierung</label><select id="capacity-network-sort" onChange={(event) => { setNetworkSort(event.target.value as typeof networkSort); setSelectedNetworkId(null); }} value={networkSort}><option value="burst">Burst Load</option><option value="reserve">Geringste Reserve</option><option value="latency">Worst E2E</option></select></div>
            <NetworkTable key={networkSort} items={sortedNetworks} routes={shown.routes} onSelect={setSelectedNetworkId} selectedId={selectedNetworkId} sourceVersions={sourceVersions} />
          </>}
          {view === "messages" && <MessageTable items={shown.messages} networks={shown.networks} />}
          {view === "routes" && <RouteTable items={shown.routes} networks={shown.networks} />}
          {view === "timing" && <TimingAnalysis results={shown} />}
          {view === "critical" && <RouteTable items={critical} networks={shown.networks} />}
          {view === "gateways" && (
            shown.gateways.length ? <PaginatedResults items={shown.gateways} label="Gateways">{(entries) => <div className="analysis-list">
              {entries.map((gateway, index) => (
                <div key={String(gateway.gateway_id ?? index)}><strong>{String(gateway.name ?? gateway.gateway_id)}</strong><span>{String(gateway.route_count ?? 0)} Routen · {String(gateway.processing_delay_ms ?? 0)} ms Verarbeitung</span></div>
              ))}
            </div>}</PaginatedResults> : <EmptyAnalysis text="Keine Gateway-Hops in den aktuellen Routen." />
          )}
          {view === "recommendations" && (
            <RecommendationList proposals={proposals} findings={findings} />
          )}
        </>
      ) : (
        <EmptyAnalysis text="Noch keine Analyse vorhanden. Starte die erste belastbare Berechnung." />
      )}

      <div className="analysis-footer-actions">
        <Link className="button secondary" href={withProjectParam("/studio?mode=parameters", initialProjectId)}>Parameter öffnen</Link>
        <Link className="button primary" href={withProjectParam("/studio/validation", initialProjectId)}>Weiter zum Preflight →</Link>
      </div>
    </section>
  );
}

function emptyWarningInfo(): ViewWarningInfo {
  return CAPACITY_VIEWS.reduce((acc, view) => ({ ...acc, [view]: { count: 0, reasons: [] } }), {} as ViewWarningInfo);
}

function addWarning(info: ViewWarningInfo, view: View, reason: string) {
  info[view].count += 1;
  if (!info[view].reasons.includes(reason)) info[view].reasons.push(reason);
}

function capacityNetworkName(item: { network_id?: unknown; network_name?: unknown }, networks: CapacityNetwork[] = []) {
  const network = networks.find((candidate) => candidate.network_id === item.network_id);
  return String(network?.network_name || item.network_name || item.network_id || "—");
}

function readableCapacityFinding(message: string) {
  return message
    .replace(/^network_transmission_ms:\s*/i, "Übertragungszeit im Netz: ")
    .replace(/\bnetwork_transmission_ms\b/gi, "Übertragungszeit im Netz")
    .replace(/\bend_to_end_latency_ms\b/gi, "End-to-End-Latenz")
    .replace(/\bburst_load_percent\b/gi, "Burst-Last")
    .replace(/\baverage_load_percent\b/gi, "Durchschnittslast")
    .replace(/\bcapacity_reserve_percent\b/gi, "Kapazitätsreserve");
}

function buildCapacityWarningInfo(
  results: CapacityResults | null,
  findings: AnalysisFinding[],
  proposals: Array<Record<string, unknown>>,
  workflowStatus: WorkflowStatus | null,
  outdatedReason: string,
): ViewWarningInfo {
  const info = emptyWarningInfo();
  if (!results) return info;

  const effectiveStatus = workflowStatus ?? results.overview.status;
  const loadCounts = results.overview.load_status_counts;
  if ((loadCounts.WARNING ?? 0) > 0) addWarning(info, "networks", `${loadCounts.WARNING} Netze im Status WARNING.`);
  if ((loadCounts.CRITICAL ?? 0) > 0) addWarning(info, "critical", `${loadCounts.CRITICAL} Netze im Status CRITICAL.`);
  if ((loadCounts.OVERLOAD ?? 0) > 0) addWarning(info, "critical", `${loadCounts.OVERLOAD} Netze im Status OVERLOAD.`);

  const issueFindings = findings.filter((finding) => finding.severity === "ERROR" || finding.severity === "WARNING");
  for (const finding of issueFindings) {
    const readableMessage = readableCapacityFinding(finding.message);
    addWarning(info, "overview", readableMessage);
    addWarning(info, "recommendations", finding.recommendation ? readableCapacityFinding(finding.recommendation) : readableMessage);
  }
  if (proposals.length > 0) addWarning(info, "recommendations", `${proposals.length} deterministische Vorschläge zur Kapazitätsoptimierung offen.`);

  for (const network of results.networks) {
    if (network.status !== "NORMAL" || network.target_status === "EXCEEDED") {
      if (network.capacity_applicable === false) {
        addWarning(info, "networks", `${capacityNetworkName(network)}: direkte Signalleitung; Buslast nicht anwendbar, Reaktionszeit nicht nachgewiesen.`);
        continue;
      }
      const target = network.target_bus_load_percent == null ? "" : ` Ziel ${network.target_bus_load_percent.toFixed(2)} %`;
      addWarning(info, "networks", `${capacityNetworkName(network)}: ${network.status}, Burst ${network.burst_load_percent.toFixed(2)} %.${target}`);
      addWarning(info, "overview", `${capacityNetworkName(network)} verursacht Netz-Warnung.`);
    }
  }

  for (const route of results.routes) {
    if (route.capacity_applicable === false) continue;
    if (route.status !== "NORMAL" || route.latency_status === "FAIL" || route.jitter_status === "FAIL" || route.requirement_status === "FAIL") {
      addWarning(info, "routes", `${route.name}: ${route.status}, Peak ${route.peak_load_percent.toFixed(2)} %, E2E ${route.end_to_end_latency_ms.toFixed(3)} ms.`);
    }
    if (route.latency_status === "FAIL" || route.jitter_status === "FAIL" || route.requirement_status === "FAIL") {
      addWarning(info, "timing", `${route.name}: Timing-Anforderung verletzt.`);
    }
  }

  for (const message of results.messages) {
    const status = String(message.status ?? message.requirement_status ?? message.validation_status ?? "").toUpperCase();
    const load = Number(message.burst_load_percent ?? message.peak_load_percent ?? message.average_load_percent ?? 0);
    if (["WARNING", "CRITICAL", "OVERLOAD", "ERROR", "FAIL"].includes(status) || load > 60) {
      addWarning(info, "messages", `${String(message.name ?? message.message_id ?? "Message")}: ${status || "Last auffällig"}${load ? `, ${load.toFixed(2)} %` : ""}.`);
    }
  }

  if ((results.timing?.deadline_violations ?? 0) > 0) addWarning(info, "timing", `${results.timing?.deadline_violations} Deadline-Verletzungen.`);
  if ((results.timing?.jitter_violations ?? 0) > 0) addWarning(info, "timing", `${results.timing?.jitter_violations} Jitter-Verletzungen.`);
  if (results.reliability?.status === "FAIL") addWarning(info, "timing", "Reliability-Anforderung nicht erfüllt.");
  if (results.synchronization?.status === "FAIL") addWarning(info, "timing", "Synchronisations-Anforderung nicht erfüllt.");

  for (const gateway of results.gateways) {
    const status = String(gateway.status ?? "").toUpperCase();
    if (["WARNING", "CRITICAL", "OVERLOAD", "ERROR", "FAIL"].includes(status)) {
      addWarning(info, "gateways", `${String(gateway.name ?? gateway.gateway_id ?? "Gateway")}: ${status}.`);
    }
  }
  for (const bottleneck of results.bottlenecks) {
    const component = String(bottleneck.component ?? bottleneck.name ?? "Bottleneck");
    const reason = `${component}: ${String(bottleneck.reason ?? "Engpass erkannt")}.`;
    addWarning(info, /gateway|bcm/i.test(component) ? "gateways" : "critical", reason);
    addWarning(info, "recommendations", reason);
  }

  for (const route of results.critical_paths) {
    addWarning(info, "critical", `${route.name}: ${route.status}, Burst ${route.burst_load_percent.toFixed(2)} %.`);
  }
  if (effectiveStatus === "WARNING" || effectiveStatus === "ERROR") {
    if (outdatedReason) {
      addWarning(info, "overview", outdatedReason);
    } else if (info.overview.reasons.length === 0) {
      const affectedViews = CAPACITY_VIEWS.filter((view) => view !== "overview" && info[view].count > 0);
      const affectedLabels = affectedViews.map((view) => CAPACITY_VIEW_LABELS[view]).join(", ");
      addWarning(info, "overview", affectedLabels
        ? `Workflowstatus ${effectiveStatus}: Ursache in ${affectedLabels} sichtbar.`
        : `Workflowstatus ${effectiveStatus}: Kein konkreter Capacity-Befund im Ergebnis enthalten; Berechnung und Workflow-Quelle synchronisieren.`);
    }
  }
  // Stored snapshots can still contain technical IDs in their finding text.
  // Resolve complete IDs against this snapshot without changing stored keys.
  const names = new Map(results.networks.filter((network) => network.network_id && network.network_name)
    .map((network) => [network.network_id, capacityNetworkName(network)]));
  if (names.size) {
    const identifiers = [...names.keys()].sort((a, b) => b.length - a.length)
      .map((identifier) => identifier.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
    const pattern = new RegExp(`(^|[^\\w-])(${identifiers.join("|")})(?![\\w-])`, "g");
    for (const view of CAPACITY_VIEWS) {
      info[view].reasons = info[view].reasons.map((reason) => reason.replace(pattern,
        (_match, prefix: string, identifier: string) => `${prefix}${names.get(identifier)}`));
    }
  }
  return info;
}

function buildStatusDetails(status: WorkflowStatus | null, info: ViewWarningInfo) {
  if (!status || (status !== "WARNING" && status !== "ERROR")) return [];
  const details = CAPACITY_VIEWS.flatMap((view) =>
    info[view].reasons.slice(0, 3).map((reason) => `${CAPACITY_VIEW_LABELS[view]}: ${reason}`),
  );
  return details.length ? details.slice(0, 6) : [`Status ${status}: Bitte betroffene Capacity-Ansichten prüfen.`];
}

function CapacityViewWarnings({ label, scenarioActive, sourceVersions, warning }: { label: string; scenarioActive: boolean; sourceVersions: Record<string, number> | null; warning: { count: number; reasons: string[] } }) {
  if (warning.count === 0) return null;
  const sourceText = capacitySourceText(sourceVersions, scenarioActive);
  const meaningText = capacityMeaningText(label, warning.reasons);
  const evidenceOnly = warning.reasons.every(isOpenEvidenceReason);
  return (
    <section className={`capacity-warning-origin${evidenceOnly ? " capacity-warning-origin-open" : ""}`} aria-label={`${evidenceOnly ? "Offene Nachweise" : "Warnursprung"} ${label}`}>
      <div>
        <strong>{evidenceOnly ? "Nachweise offen" : "Warnursprung"}: {label}</strong>
        <span>{warning.count} Hinweis{warning.count === 1 ? "" : "e"} in dieser Ansicht</span>
      </div>
      <dl className="capacity-warning-explanation">
        <div><dt>Quelle der Bewertung</dt><dd>{sourceText}</dd></div>
        <div><dt>Gemeint ist</dt><dd>{meaningText}</dd></div>
      </dl>
      <ul>
        {warning.reasons.slice(0, 8).map((reason, index) => <li key={`${reason}-${index}`}>{reason}</li>)}
      </ul>
      {warning.reasons.length > 8 && <small>{warning.reasons.length - 8} weitere Hinweise in den Detailtabellen.</small>}
    </section>
  );
}

function capacitySourceText(sourceVersions: Record<string, number> | null, scenarioActive: boolean) {
  const versionLabels: Record<string, string> = {
    engineering_model: "Engineering-Modell",
    routing: "Routing",
    network_editor: "Netzwerk-Editor",
    parameters: "Parameter",
  };
  const versions = sourceVersions
    ? ["engineering_model", "routing", "network_editor", "parameters"].map((key) => `${versionLabels[key]} v${sourceVersions[key] ?? 0}`).join(", ")
    : "aktuelle Workflow-Quellen";
  const mode = scenarioActive ? "What-if-Szenario, nicht im Draft gespeichert" : "gespeicherter Capacity-Snapshot";
  return `${mode}; berechnet aus Nachrichtenlänge/DLC, Zykluszeiten, Routen, Bustechnik, Bitrate, Burst-Faktor und Queue-Policy (${versions}).`;
}

function isOpenEvidenceReason(reason: string) {
  return /\b(fehlt|fehlen|offen|unvollständig|nicht nachgewiesen|nicht ableitbar|kein deterministisches scheduling-modell|zeitnachweis)\b/i.test(reason)
    && !/\b(überschreit|verletzt|overload|critical|engpass|zu viel|außerhalb)\b/i.test(reason);
}

function capacityMeaningText(label: string, reasons: string[]) {
  const joined = reasons.join(" ").toLowerCase();
  if (reasons.length > 0 && reasons.every(isOpenEvidenceReason)) {
    return "Diese Hinweise bezeichnen fehlende Eingabedaten oder noch offene Zeitnachweise. Sie sind keine Last-, Ziel- oder Plausibilitätsverletzungen; berechnete Auslastung und Reserve werden davon getrennt bewertet.";
  }
  if (joined.includes("network_transmission_ms") || joined.includes("engpass")) {
    return "Mindestens eine Uebertragung belegt im aktuellen Netz rechnerisch zu viel Zeit oder Reserve. Die Detailtabellen zeigen, welche Route, Message oder welches Netz den Engpass erzeugt.";
  }
  if (label === "Kritisch") {
    return "Diese Ansicht sammelt Befunde, die vor Simulation oder Freigabe geprueft werden sollen: Engpaesse, Timingverletzungen, zu geringe Reserve oder auffaellige Burst-Last.";
  }
  if (label === "Empfehlungen") {
    return "Hier landen technische Optimierungshinweise aus der gleichen Rechnung; sie sind Vorschlaege und muessen fachlich freigegeben werden.";
  }
  return "Die Hinweise stammen aus der Capacity-&-Timing-Auswertung. Die Einträge benennen jeweils konkret, ob eine Grenze verletzt, ein Modell widersprüchlich oder ein Nachweis noch offen ist.";
}

function Metric({ label, value, tone, details = [] }: { label: string; value: string; tone?: string; details?: string[] }) {
  return (
    <div className={tone ? `metric metric-${tone.toLowerCase()}` : "metric"} tabIndex={details.length ? 0 : undefined}>
      <span>{label}</span>
      <strong>{value}</strong>
      {details.length > 0 && (
        <div className="metric-hint" role="tooltip">
          <b>Ursprung</b>
          {details.map((detail, index) => <small key={`${detail}-${index}`}>{detail}</small>)}
        </div>
      )}
    </div>
  );
}

function PaginatedResults<T>({ items, label, children, onPageChange }: {
  items: readonly T[];
  label: string;
  children(items: T[]): ReactNode;
  onPageChange?(): void;
}) {
  const [requestedPage, setPage] = useState(0);
  const container = useRef<HTMLDivElement>(null);
  const current = paginateCapacityItems(items, requestedPage);
  useEffect(() => { setPage(current.page); }, [current.page]);

  function changePage(page: number) {
    setPage(page);
    onPageChange?.();
    container.current?.scrollIntoView({ block: "start" });
  }

  return <div className="capacity-paginated-results" ref={container}>
    {children(current.items)}
    {current.pageCount > 1 && <nav aria-label={`${label}: Seitennavigation`} className="table-pagination capacity-pagination">
      <span aria-live="polite">{current.first}-{current.last} von {current.total}</span>
      <div>
        <button aria-label="Vorherige Seite" className="button secondary tiny" disabled={current.page === 0} onClick={() => changePage(current.page - 1)} title="Vorherige Seite" type="button">←</button>
        <span>Seite {current.page + 1} / {current.pageCount}</span>
        <button aria-label="Nächste Seite" className="button secondary tiny" disabled={current.page + 1 >= current.pageCount} onClick={() => changePage(current.page + 1)} title="Nächste Seite" type="button">→</button>
      </div>
    </nav>}
  </div>;
}

function RecommendationList({ proposals, findings }: { proposals: Array<Record<string, unknown>>; findings: AnalysisFinding[] }) {
  const items = [
    ...proposals.map((proposal) => ({ kind: "proposal" as const, proposal })),
    ...findings.map((finding) => ({ kind: "finding" as const, finding })),
  ];
  if (!items.length) return <EmptyAnalysis text="Keine Kapazitätsauffälligkeiten gefunden." />;
  return <PaginatedResults items={items} label="Empfehlungen">{(entries) => <div className="analysis-list findings-list">
    {entries.map((item, index) => item.kind === "proposal"
      ? <CapacityProposal proposal={item.proposal} index={index} />
      : <div className={`finding finding-${item.finding.severity.toLowerCase()}`} key={`finding-${item.finding.code}-${index}`}><span>{item.finding.severity}</span><strong>{item.finding.message}</strong><small>{item.finding.recommendation ?? "Keine Aktion erforderlich."}</small></div>)}
  </div>}</PaginatedResults>;
}

function CapacityProposal({ proposal, index }: { proposal: Record<string, unknown>; index: number }) {
  const branch = typeof proposal.branch_analysis === "object" && proposal.branch_analysis !== null
    ? proposal.branch_analysis as Record<string, unknown>
    : {};
  const inventory = typeof proposal.protocol_inventory === "object" && proposal.protocol_inventory !== null
    ? proposal.protocol_inventory as Record<string, unknown>
    : {};
  const constraint = typeof proposal.inventory_constraint === "object" && proposal.inventory_constraint !== null
    ? proposal.inventory_constraint as Record<string, unknown>
    : {};
  const selectedProtocol = String(constraint.protocol ?? branch.selected_protocol ?? branch.protocol ?? "unbekannt");
  const stock = Object.keys(constraint).length
    ? constraint
    : typeof inventory[selectedProtocol] === "object" && inventory[selectedProtocol] !== null
    ? inventory[selectedProtocol] as Record<string, unknown>
    : {};
  const current = Number(branch.current_load_percent);
  const projected = Number(branch.projected_max_load_percent);
  const loadText = Object.keys(constraint).length
    ? `Bestand ${String(constraint.used ?? 0)} / ${String(constraint.provisioned ?? 0)}, Überschreitung ${String(constraint.excess ?? 0)}`
    : Number.isFinite(current)
    ? `${current.toFixed(2)} % aktuell${Number.isFinite(projected) ? ` → ${projected.toFixed(2)} % prognostiziert` : ""}`
    : "Lastdaten werden bei der Freigabe erneut geprüft";
  const stockText = Object.keys(stock).length
    ? `${selectedProtocol}: ${String(stock.free ?? 0)} frei / ${String(stock.provisioned ?? 0)} vorgesehen`
    : `${selectedProtocol}: Bestand nicht explizit begrenzt`;
  return <div className="finding finding-info" key={`proposal-${String(proposal.id ?? index)}`}>
    <span>DETERMINISTISCHER VORSCHLAG</span>
    <strong>{String(proposal.summary)}</strong>
    <small>{String(proposal.kind)} · {loadText} · {stockText} · Freigabe erforderlich</small>
  </div>;
}

function NetworkTable({ items, routes, onSelect, selectedId, sourceVersions }: { items: CapacityResults["networks"]; routes: CapacityResults["routes"]; onSelect: (id: string | null) => void; selectedId: string | null; sourceVersions: Record<string, number> | null }) {
  if (!items.length) return <EmptyAnalysis text="Keine Netze mit zugeordneten Routen vorhanden." />;
  return (
    <PaginatedResults items={items} label="Netze" onPageChange={() => onSelect(null)}>{(entries) => <div className="analysis-table-wrap"><table className="analysis-table capacity-network-table"><thead><tr><th>Netz</th><th>Technologie</th><th>Ø Load</th><th>Peak</th><th>Reserve</th><th>Bus-Antwortgrenze</th><th>Status</th></tr></thead><tbody>
      {entries.map((item) => {
        const expanded = selectedId === item.network_id;
        const detailId = `capacity-network-${item.network_id}`;
        const toggle = () => onSelect(expanded ? null : item.network_id);
        return <Fragment key={item.network_id}>
          <tr className={`capacity-network-row${expanded ? " selected" : ""}`} onClick={toggle}>
            <td><button aria-controls={expanded ? detailId : undefined} aria-expanded={expanded} className="capacity-network-toggle" onClick={(event) => { event.stopPropagation(); toggle(); }} title={expanded ? "Netzdetails schließen" : "Netzdetails öffnen"} type="button"><span aria-hidden="true">{expanded ? "▾" : "▸"}</span><strong>{capacityNetworkName(item)}</strong></button></td>
            <td>{item.protocol}</td><td>{item.capacity_applicable === false ? "n/a" : `${item.average_load_percent.toFixed(2)} %`}</td><td>{item.capacity_applicable === false ? "n/a" : `${item.peak_load_percent.toFixed(2)} %`}</td><td>{item.capacity_applicable === false ? "n/a" : `${item.capacity_reserve_percent.toFixed(2)} %`}</td><td>{item.timing_verified && item.response_time_bound_ms != null ? `${item.response_time_bound_ms.toFixed(3)} ms` : "Nicht nachgewiesen"}</td><td><span className={`load-status load-${item.status.toLowerCase()}`}>{item.status}</span></td>
          </tr>
          {expanded && <tr className="capacity-network-detail-row"><td colSpan={7}><NetworkDetail id={detailId} network={item} routes={routes.filter((route) => route.network_id === item.network_id)} sourceVersions={sourceVersions} /></td></tr>}
        </Fragment>;
      })}
    </tbody></table></div>}</PaginatedResults>
  );
}

function NetworkDetail({ id, network, routes, sourceVersions }: { id: string; network: CapacityNetwork; routes: CapacityResults["routes"]; sourceVersions: Record<string, number> | null }) {
  const contributors = network.top_contributors ?? routes.slice(0, 5).map((route) => ({ route_id: route.route_id, name: route.name, load_percent: route.average_load_percent }));
  return (
    <section aria-label={`Netzdetails ${capacityNetworkName(network)}`} className="network-capacity-detail" id={id}>
      <div><p className="eyebrow">Netzdetails</p><h3>{capacityNetworkName(network)}</h3><span>{network.protocol} · {network.bitrate ? `${network.bitrate.toLocaleString("de-DE")} bit/s` : "historischer Snapshot"}</span></div>
      <dl className="overview-list"><div><dt>Burst</dt><dd>{network.capacity_applicable === false ? "n/a" : `${network.burst_load_percent.toFixed(2)} %`}</dd></div><div><dt>Margin</dt><dd>{network.capacity_applicable === false ? "n/a" : `${(network.capacity_margin_percent ?? 100 - network.burst_load_percent).toFixed(2)} %`}</dd></div><div><dt>Routen</dt><dd>{routes.length}</dd></div></dl>
      {network.evaluation && <div className="capacity-evaluation" aria-label="Getrennte Netzbewertung">
        <dl className="overview-list">
          <div><dt>Nutzlast / Kodierung</dt><dd>{network.evaluation.payload.status === "PASS" ? "Passend" : network.evaluation.payload.status === "FAIL" ? `${network.evaluation.payload.errors} Fehler` : "Offen"}</dd></div>
          <div><dt>{network.evaluation.capacity.basis === "BOUNDED_EVENT_DEMAND" ? "Begrenzter Ereignisbedarf" : "Nominaler Kapazitätsbedarf"}</dt><dd>{network.capacity_applicable === false ? "Nicht anwendbar" : `${network.evaluation.capacity.load_percent.toFixed(2)} %`}</dd></div>
          <div><dt>Busplan</dt><dd>{network.evaluation.schedule.status === "FEASIBLE_UNDER_ASSUMPTIONS" ? "Machbar unter Annahmen" : "Nicht nachgewiesen"}{network.evaluation.schedule.slot_load_percent != null && ` · ${network.evaluation.schedule.slot_load_percent.toFixed(2)} % Slots`}</dd></div>
          <div><dt>Stressszenario</dt><dd>{network.evaluation.stress.status === "UNVERIFIED" ? "Nicht anwendbar" : network.evaluation.stress.status === "PASS" ? "Im Planungsziel" : "Planungsziel überschritten"}</dd></div>
          <div><dt>Funktionale Reaktionszeit</dt><dd>{network.evaluation.functional.status === "PASS" ? "Vorgabe eingehalten" : network.evaluation.functional.status === "FAIL" ? "Vorgabe verletzt" : "Nicht nachgewiesen"}</dd></div>
        </dl>
        <p className="muted">Slotreservierung und Stressfaktor sind verschiedene Bewertungen. {network.evaluation.functional.explanation}</p>
      </div>}
      <NetworkSignalInspection networkId={network.network_id} sourceVersions={sourceVersions} />
      {network.capacity_applicable !== false && <PaginatedResults items={contributors} label="Lastbeiträge">{(entries) => <div className="capacity-contributors"><strong>Top Contributors</strong>{entries.map((item) => <span key={item.route_id}>{item.name}<b>{item.load_percent.toFixed(2)} %</b></span>)}</div>}</PaginatedResults>}
      <RouteTable items={routes} networks={[network]} />
    </section>
  );
}

function NetworkSignalInspection({ networkId, sourceVersions }: { networkId: string; sourceVersions: Record<string, number> | null }) {
  const [inspection, setInspection] = useState<NetworkInspection | null>(null);
  const [error, setError] = useState("");
  const requestId = useRef(0);
  const lastSource = useRef<Awaited<ReturnType<typeof getCapacityInspectionSources>> | null>(null);
  const lastNetwork = useRef("");
  const inFlight = useRef<string | null>(null);
  const mounted = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; ++requestId.current; inFlight.current = null; }; }, []);
  const load = useCallback(async () => {
    const projectId = readActiveProjectId();
    if (inFlight.current === projectId) return;
    const current = ++requestId.current;
    inFlight.current = projectId;
    try {
      const data = await getCapacityInspectionSources(projectId);
      if (!mounted.current || current !== requestId.current || projectId !== readActiveProjectId()) return;
      if (lastSource.current !== data || lastNetwork.current !== networkId) {
        lastSource.current = data;
        lastNetwork.current = networkId;
        setInspection(buildNetworkInspection(networkId, data));
      }
      setError("");
    } catch (caught) {
      if (mounted.current && current === requestId.current && projectId === readActiveProjectId()) setError(caught instanceof Error ? caught.message : "Signalprüfung nicht verfügbar.");
    } finally {
      if (current === requestId.current) inFlight.current = null;
    }
  }, [networkId]);
  useWorkflowRefresh(load);
  const value = (number: number | null) => number === null ? "Offen" : number.toLocaleString("de-DE", { maximumFractionDigits: 8 });
  if (!inspection) return <div className="capacity-signal-inspection">{error ? <><p className="notice error">{error}</p><button className="button secondary tiny" type="button" onClick={() => void load()}>Erneut prüfen</button></> : <p role="status">Teilnehmer und Signalkonfiguration werden geprüft …</p>}</div>;
  const differs = sourceVersions && ["engineering_model", "routing", "network_editor"].some((key) => sourceVersions[key] !== inspection.versions[key]);
  return <div className="capacity-signal-inspection">
    <h4>Teilnehmer und Systemrahmen</h4>
    <p className="capacity-inspection-summary">{inspection.counts.senders} Sender · {inspection.counts.participants} Teilnehmer · {inspection.counts.systems} Systemrahmen · {inspection.counts.messages} Nachrichten · {inspection.counts.signals} Signale</p>
    {error && <p className="notice error">{error} Letzter Prüfstand bleibt sichtbar.</p>}
    {differs && <p className="notice warning">Die Signalprüfung verwendet einen neueren Modellstand als die Lastberechnung. Capacity & Timing erneut berechnen.</p>}
    {inspection.notices.map((notice, index) => <p className="notice warning" key={index}>{notice}</p>)}
    <PaginatedResults items={inspection.participants} label="Netzteilnehmer">{(items) => <div className="analysis-table-wrap"><table className="analysis-table capacity-participants-table"><thead><tr><th>Teilnehmer</th><th>Rolle im Netz</th><th>Interface</th><th>Systemrahmen</th></tr></thead><tbody>{items.map((item) => <tr key={item.id}><td><strong>{item.name}</strong><small>{item.type}</small></td><td>{item.roles.filter((role) => role !== "Physisch verbunden" || item.roles.length === 1).join(", ")}</td><td>{item.interfaces.map((port) => <span className="capacity-interface-name" key={port.id}>{port.name}</span>)}</td><td>{item.system ? <>{item.system.name}<small>{item.system.basis === "inferred" ? "Zuordnung abgeleitet, fachlich prüfen" : "Zugeordnet"}</small></> : item.type === "Gateway" ? "Backbone / kein Systemrahmen" : "Zuordnung offen"}</td></tr>)}</tbody></table></div>}</PaginatedResults>

    <h4>Signalprüfung</h4>
    <p className="capacity-inspection-summary">{inspection.counts.passed} rechnerisch passend · {inspection.counts.warnings} Optimierungshinweise · {inspection.counts.errors} fehlerhaft · {inspection.counts.open + inspection.counts.missingSignals} offen</p>
    <PaginatedResults items={inspection.signals} label="Signalprüfung">{(items) => <div className="analysis-table-wrap"><table className="analysis-table capacity-signals-table"><thead><tr><th>Signal / Nachricht</th><th>Konfiguration</th><th>Wertebereich / Skalierung</th><th>Bitbedarf</th><th>Prüfergebnis</th></tr></thead><tbody>{items.map((signal) => <tr key={signal.id}><td><strong>{signal.name}</strong><small>{signal.messageName}</small></td><td>{signal.semanticType} · {signal.dataType || "Datentyp offen"} · {value(signal.bits)} Bit<small>Startbit {value(signal.start)} · {signal.byteOrder === "little_endian" ? "Intel / Little Endian" : signal.byteOrder === "big_endian" ? "Motorola / Big Endian" : "Byte-Reihenfolge offen"}</small></td><td>{value(signal.min)} bis {value(signal.max)} {signal.unit}<small>Faktor {value(signal.factor)} · Offset {value(signal.offset)}</small></td><td>{signal.requiredBits === null ? "Nicht belegt" : `${signal.requiredBits} Bit rechnerisch`}<small>{signal.bits !== null && signal.requiredBits !== null ? `${signal.bits} Bit konfiguriert` : ""}</small></td><td><span className={`load-status capacity-check-${signal.status.toLowerCase()}`}>{({ PASS: "PASSEND", ERROR: "FEHLER", WARNING: "PRÜFEN", OPEN: "OFFEN" })[signal.status]}</span>{signal.checks.length ? <ul className="capacity-check-findings">{signal.checks.map((check, index) => <li key={`${check.code}-${index}`}>{check.text}</li>)}</ul> : <small>Wertebereich, Skalierung und Bitbelegung rechnerisch konsistent.</small>}</td></tr>)}</tbody></table></div>}</PaginatedResults>

    <h4>Nachrichtenbelegung</h4>
    <PaginatedResults items={inspection.messages} label="Nachrichtenbelegung">{(items) => <div className="analysis-table-wrap"><table className="analysis-table"><thead><tr><th>Nachricht / Ursprung</th><th>Signale</th><th>Payload</th><th>Belegte Signalbits</th><th>Belegungsprüfung</th></tr></thead><tbody>{items.map((message) => <tr key={message.id}><td><strong>{message.name}</strong><small>{message.origin}</small></td><td>{message.signalCount}</td><td>{value(message.bytes)} Byte</td><td>{value(message.occupiedBits)} Bit</td><td>{message.minimumBytes !== null && message.bytes !== null ? <>{message.minimumBytes} Byte bis zum letzten belegten Bit{message.bytes > message.minimumBytes && <small>{message.bytes - message.minimumBytes} Byte am Ende ohne zugeordnete Signalbits. Padding, Prüfsumme und Protokollvorgaben vor einer DLC-Reduktion prüfen.</small>}</> : "Belegung nicht abschließend prüfbar"}</td></tr>)}</tbody></table></div>}</PaginatedResults>
    <p className="analysis-footnote">Prüfgrundlage: aktuelles Engineering-Modell. Rechnerische Hinweise sind keine technische Freigabe; Signale und Nachrichten bleiben unverändert.</p>
  </div>;
}

function responseBound(route: CapacityResults["routes"][number]) {
  return route.timing_verified && route.response_time_bound_ms != null ? `${route.response_time_bound_ms.toFixed(3)} ms` : "Nicht nachgewiesen";
}

function RouteTable({ items, networks }: { items: CapacityResults["routes"]; networks: CapacityNetwork[] }) {
  if (!items.length) return <EmptyAnalysis text="Keine passenden Routen vorhanden." />;
  return (
    <PaginatedResults items={items} label="Routen">{(entries) => <div className="analysis-table-wrap"><table className="analysis-table"><thead><tr><th>Route</th><th>Netz</th><th>Payload / Cycle</th><th>Peak</th><th>E2E-Antwortgrenze</th><th>Modell</th></tr></thead><tbody>
      {entries.map((item) => <tr key={item.route_id}><td><strong>{item.name}</strong><small>{item.route_code}</small></td><td>{capacityNetworkName(item, networks)}</td><td>{item.payload_bytes} B / {item.cycle_ms} ms</td><td>{item.capacity_applicable === false ? "n/a" : `${item.peak_load_percent.toFixed(2)} %`}</td><td>{responseBound(item)}</td><td><code>{item.calculation_model}</code></td></tr>)}
    </tbody></table></div>}</PaginatedResults>
  );
}

function MessageTable({ items, networks }: { items: CapacityResults["messages"]; networks: CapacityNetwork[] }) {
  if (!items.length) return <EmptyAnalysis text="Keine Messages mit Timingdaten vorhanden." />;
  return (
    <PaginatedResults items={items} label="Messages">{(entries) => <div className="analysis-table-wrap"><table className="analysis-table"><thead><tr><th>Message</th><th>Netz</th><th>Technologie</th><th>Payload / Cycle</th><th>Ø Load</th><th>Peak</th><th>Modell</th></tr></thead><tbody>
      {entries.map((item, index) => <tr key={String(item.message_id ?? index)}><td><strong>{String(item.name ?? item.message_id)}</strong></td><td>{capacityNetworkName(item, networks)}</td><td>{String(item.protocol ?? "—")}</td><td>{String(item.payload_bytes ?? "—")} B / {String(item.cycle_ms ?? "—")} ms</td><td>{["GPIO", "PWM"].includes(String(item.protocol ?? "").toUpperCase()) ? "n/a" : `${Number(item.average_load_percent ?? 0).toFixed(2)} %`}</td><td>{["GPIO", "PWM"].includes(String(item.protocol ?? "").toUpperCase()) ? "n/a" : `${Number(item.peak_load_percent ?? 0).toFixed(2)} %`}</td><td><code>{String(item.calculation_model ?? "—")}</code></td></tr>)}
    </tbody></table></div>}</PaginatedResults>
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
        <Metric label="Geschätztes Queueing" value={`${worstQueue.toFixed(3)} ms`} />
        <Metric label="Geschätzter Jitter" value={`${worstJitter.toFixed(3)} ms`} />
        <Metric label="Queue Policy" value={timing?.queue_policy ?? "FIFO"} />
        <Metric label="Retransmission" value={`${((reliability?.configured_retransmission_rate ?? 0) * 100).toFixed(2)} %`} />
        <Metric label="Clock Drift" value={`${synchronization?.clock_drift_ppm ?? 0} ppm`} />
        <Metric label="Sync Precision" value={`${synchronization?.sync_precision_ms ?? 0} ms`} />
      </div>
      <PaginatedResults items={results.routes} label="Timing">{(entries) => <div className="analysis-table-wrap"><table className="analysis-table"><thead><tr><th>Route</th><th>Transmission</th><th>Queueing (Schätzung)</th><th>Gateway</th><th>E2E-Antwortgrenze</th><th>Jitter (Schätzung) / Budget</th><th>Deadline</th></tr></thead><tbody>
        {entries.map((route) => <tr key={route.route_id}><td><strong>{route.name}</strong><small>{route.route_code}</small></td><td>{(route.transmission_latency_ms ?? 0).toFixed(3)} ms</td><td>{route.queueing_latency_ms.toFixed(3)} ms</td><td>{(route.gateway_latency_ms ?? 0).toFixed(3)} ms</td><td>{responseBound(route)}</td><td>{(route.estimated_jitter_ms ?? 0).toFixed(3)} / {route.jitter_budget_ms ? `${route.jitter_budget_ms.toFixed(3)} ms` : "—"}</td><td>{route.max_latency_ms ? `${route.max_latency_ms} ms` : "—"}</td></tr>)}
      </tbody></table></div>}</PaginatedResults>
      {synchronization && (
        <p className="analysis-footnote">Maximale Drift im Beobachtungsfenster: <strong>{synchronization.max_drift_over_observation_ms.toFixed(3)} ms</strong> bei {synchronization.observation_s} s.</p>
      )}
    </div>
  );
}

function EmptyAnalysis({ text }: { text: string }) {
  return <div className="analysis-empty"><strong>Noch keine auswertbaren Daten</strong><p>{text}</p></div>;
}

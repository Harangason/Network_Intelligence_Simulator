"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { getSimulation, listSimulations } from "@/shared/api/api";
import { mergeSimulationResult, mergeSimulationSnapshots, selectSimulationSnapshot } from "@/features/simulation/lib/simulation-result";
import type { ModelSimulationTrace, RuntimeMetrics, RuntimeNetworkMetric, RuntimeRouteMetric, SimulationJob } from "@/shared/api/types";
import {
  getWorkflowSimulationSnapshot,
  getWorkflowSnapshots,
  setWorkflowContext,
  type AnalysisSnapshot,
  type SimulationSnapshot,
} from "@/features/workflow/lib/workflow-api";
import { useWorkflowRefresh } from "@/features/workflow/lib/use-workflow-refresh";
import { readActiveProjectId, withProjectParam } from "@/features/settings/lib/user-settings";
import { simulationPage } from "@/features/simulation/lib/simulation-pagination";
import { SimulationPageControls } from "@/features/simulation/ui/simulation-page-controls";
import { RuntimeModelViews, RuntimeTrendTools } from "./runtime-chart-tools";
import { forecastUnderAssumptions } from "./runtime-chart-data";

export function ResultsWorkbench({ initialProjectId = "", initialSnapshotId }: { initialProjectId?: string; initialSnapshotId?: string }) {
  const [snapshots, setSnapshots] = useState<SimulationSnapshot[]>([]);
  const [capacity, setCapacity] = useState<AnalysisSnapshot | null>(null);
  const [jobs, setJobs] = useState<Record<string, SimulationJob>>({});
  const [selectedId, setSelectedId] = useState<string | null>(initialSnapshotId ?? null);
  const requestedSnapshot = useRef(initialSnapshotId);
  const loadSequence = useRef(0);
  const [compareId, setCompareId] = useState<string>("");
  const [snapshotQuery, setSnapshotQuery] = useState("");
  const [snapshotStatus, setSnapshotStatus] = useState("");
  const [snapshotPage, setSnapshotPage] = useState(0);
  const [error, setError] = useState("");
  const [loadedSnapshotDetails, setLoadedSnapshotDetails] = useState<Set<string>>(() => new Set());

  const load = useCallback(async () => {
    const sequence = ++loadSequence.current;
    const projectId = initialProjectId || readActiveProjectId();
    try {
      const [workflowSnapshots, simulationJobs] = await Promise.all([getWorkflowSnapshots(projectId), listSimulations(projectId)]);
        if (sequence !== loadSequence.current || readActiveProjectId() !== projectId) return;
        const selection = selectSimulationSnapshot(workflowSnapshots.simulations, { snapshotId: requestedSnapshot.current });
        setSnapshots((current) => mergeSimulationSnapshots(workflowSnapshots.simulations, current));
        setCapacity(workflowSnapshots.capacity);
        setJobs(Object.fromEntries(simulationJobs.map((job) => [job.id, job])));
        requestedSnapshot.current = selection?.id;
        setSelectedId(selection?.id ?? null);
        setError("");
    } catch (caught) {
      if (sequence === loadSequence.current) setError(caught instanceof Error ? caught.message : "Ergebnisse nicht verfügbar.");
    }
  }, [initialProjectId]);
  useWorkflowRefresh(load);

  const selected = useMemo(() => snapshots.find((item) => item.id === selectedId) ?? null, [selectedId, snapshots]);
  const compareSnapshot = snapshots.find((item) => item.id === compareId);
  const snapshotEntries = simulationPage(snapshots.filter(item => (!snapshotStatus || item.status === snapshotStatus)
    && `${item.id} ${item.job_id ?? ""} ${item.status} ${new Date(item.created_at).toLocaleString("de-DE")}`
      .toLocaleLowerCase().includes(snapshotQuery.trim().toLocaleLowerCase())), snapshotPage, 6);

  useEffect(() => {
    if (!selected) return;
    void setWorkflowContext({
      selected_simulation: { snapshot_id: selected.id, job_id: selected.job_id ?? null },
    }, initialProjectId || readActiveProjectId()).catch(() => undefined);
  }, [initialProjectId, selected?.id, selected?.job_id]);

  useEffect(() => {
    const ids = [selectedId, compareId].filter((value): value is string => Boolean(value));
    const missing = ids.filter((id) => {
      const snapshot = snapshots.find((item) => item.id === id);
      return snapshot && snapshot.result === undefined && !loadedSnapshotDetails.has(id);
    });
    if (!missing.length) return;
    const projectId = initialProjectId || readActiveProjectId();
    setLoadedSnapshotDetails((current) => new Set([...current, ...missing]));
    missing.forEach((id) => {
      void getWorkflowSimulationSnapshot(id, projectId)
        .then((fullSnapshot) => {
          if (readActiveProjectId() === projectId) setSnapshots((current) => current.map((item) => item.id === fullSnapshot.id ? { ...item, ...fullSnapshot } : item));
        })
        .catch((caught) => { if (readActiveProjectId() === projectId) setError(caught instanceof Error ? caught.message : "Simulationsergebnis nicht verfügbar."); });
    });
  }, [compareId, initialProjectId, selectedId, snapshots]);

  const job = selected?.job_id ? jobs[selected.job_id] : undefined;
  const observed = mergeSimulationResult(job?.result, selected?.result);
  // A historical forecast must belong to that run, never to today's capacity snapshot.
  const predictionSource = selected ? selected.calculated_metrics : capacity?.results;
  const assumptions = forecastUnderAssumptions(predictionSource);
  const predicted = predictionSource && "overview" in predictionSource
    ? (predictionSource.overview as {
        max_peak_load_percent: number | null;
        worst_end_to_end_latency_ms: number | null;
        minimum_capacity_reserve_percent: number | null;
        capacity_verified?: boolean;
        timing_verified?: boolean;
        network_count: number;
      })
    : null;
  const forecastValue = (value: unknown, verified: boolean | undefined, unit: string, digits = 2) =>
    verified === true && typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(digits)} ${unit}` : "Nachweis offen";
  const traceEvents = observed?.trace?.events;
  const runtime = observed?.runtime_metrics;
  const compareJob = compareSnapshot?.job_id ? jobs[compareSnapshot.job_id] : undefined;
  const compareRuntime = mergeSimulationResult(compareJob?.result, compareSnapshot?.result)?.runtime_metrics;
  const projectIdForLinks = initialProjectId;
  const runtimePeak = Math.max(0, ...(runtime?.networks ?? []).map((item) => item.peak_load_percent));
  const runtimeBurst = Math.max(0, ...(runtime?.networks ?? []).map((item) => item.burst_load_percent));
  const runtimeLatency = Math.max(0, ...(runtime?.routes ?? []).map((item) => item.maximum_end_to_end_latency_ms));
  const comparePeak = Math.max(0, ...(compareRuntime?.networks ?? []).map((item) => item.peak_load_percent));

  async function refreshJob() {
    if (!selected?.job_id) return;
    try {
      const next = await getSimulation(selected.job_id, initialProjectId || readActiveProjectId());
      setJobs((current) => ({ ...current, [next.id]: next }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Lauf konnte nicht aktualisiert werden.");
    }
  }

  function selectRun(id: string) {
    requestedSnapshot.current = id;
    setSelectedId(id);
    setError("");
    window.history.replaceState(window.history.state, "", withProjectParam(`/studio/results?snapshot=${encodeURIComponent(id)}`, initialProjectId || readActiveProjectId()));
  }

  return (
    <section className="results-workbench">
      <div className="analysis-toolbar"><div><p className="eyebrow">Evidence & comparison</p><h2>Results / Analysis</h2><p>Engineering-Prognose und Simulationsergebnis bleiben mit ihren Quellversionen nachvollziehbar.</p></div><div className="analysis-actions">{snapshots.length > 1 && <label className="result-compare-select"><span>Vergleichslauf</span><select onChange={(event) => setCompareId(event.target.value)} value={compareId}><option value="">Kein Vergleich</option>{snapshots.filter((item) => item.id !== selectedId).map((item) => <option key={item.id} value={item.id}>{new Date(item.created_at).toLocaleString("de-DE")}</option>)}</select></label>}{selected?.job_id && <button className="button secondary" onClick={() => void refreshJob()} type="button">Status aktualisieren</button>}</div></div>
      {error && <div className="notice error">{error}</div>}
      <div className="results-layout">
        <aside className="result-run-list">
          <div className="result-run-list-heading"><strong>SimulationSnapshots</strong><span>{snapshots.length}</span></div>
          <div className="result-run-filters">
            <label>Läufe filtern<input type="search" placeholder="Datum, Job oder Status" value={snapshotQuery} onChange={event => { setSnapshotQuery(event.target.value); setSnapshotPage(0); }} /></label>
            <label>Status<select value={snapshotStatus} onChange={event => { setSnapshotStatus(event.target.value); setSnapshotPage(0); }}><option value="">Alle Status</option>{[...new Set(snapshots.map(item => item.status))].map(value => <option key={value} value={value}>{value}</option>)}</select></label>
          </div>
          {snapshotEntries.items.map((item) => <button className={selectedId === item.id ? "active" : ""} data-snapshot-id={item.id} key={item.id} onClick={() => selectRun(item.id)} type="button"><span className={`run-state run-${item.status.toLowerCase()}`}>{item.status}</span><strong>{new Date(item.created_at).toLocaleString("de-DE")}</strong><small>{item.job_id ? `Job ${item.job_id.slice(0, 10)}` : "Noch nicht ausgeführt"}</small></button>)}
          {!!snapshots.length && !snapshotEntries.total && <p className="result-run-empty">Keine passenden Läufe.</p>}
          <SimulationPageControls label="Läufe" {...snapshotEntries} onPage={setSnapshotPage} />
          {!snapshots.length && <div className="analysis-empty"><strong>Keine Snapshots</strong><p>Nach einem erfolgreichen Preflight kann die erste Simulation gestartet werden.</p></div>}
        </aside>
        <div className="result-analysis">
          {selected ? <>
            {observed?.assessment ? <div className={`workflow-blocker ${observed.assessment.conformance === "PASS" ? "" : "warning"}`}>
              <strong>Anforderungserfüllung: {observed.assessment.conformance === "PASS" ? "Bestanden" : observed.assessment.conformance === "FAIL" ? "Nicht bestanden" : "Nicht vollständig geprüft"}</strong>
              <span>Signale im Lauf: {observed.assessment.observed_signal_count} / {observed.assessment.scope_coverage.required_signals} im gewählten Umfang. {observed.assessment.scope_coverage.excluded_signals} ausdrücklich ausgeschlossen.</span>
              {!!observed.assessment.scope_coverage.transport_exclusions?.length && <details>
                <summary>Bewusst nicht übertragen</summary>
                <p>Diese Funktionsausgänge sind ausgeschaltet und besitzen keinen Transport. Ihre interne Verarbeitung wurde in diesem Netzwerklauf nicht beobachtet.</p>
                <ul>{observed.assessment.scope_coverage.transport_exclusions.map(exclusion => <li key={exclusion.message_id}><strong>{exclusion.message_name || exclusion.message_id}</strong>: {exclusion.reason} ({exclusion.signal_ids.length} Signale)</li>)}</ul>
              </details>}
              <span>Routen: {observed.assessment.failed_route_count} verletzt, {observed.assessment.unevaluated_route_count} nicht auswertbar. Fehlende Nachweise: {observed.assessment.missing_observed_route_ids.length} Routen, {observed.assessment.missing_observed_network_ids.length} Netze.</span>
            </div> : (observed && <div className="workflow-blocker warning"><strong>Anforderungserfüllung nicht geprüft</strong><span>Für diesen Lauf fehlt eine vollständige Bewertung von Transportumfang und Anforderungen.</span></div>)}
            <div className="metric-strip"><div className="metric"><span>Snapshot</span><strong>{selected.id.slice(0, 8)}</strong></div><div className="metric"><span>Ausführung</span><strong>{job?.status ?? selected.status}</strong></div><div className="metric"><span>{predicted?.capacity_verified ? "Prognose Peak" : "Peak unter Annahmen"}</span><strong>{predicted?.capacity_verified ? forecastValue(predicted.max_peak_load_percent, true, "%") : assumptions?.peak != null ? `${assumptions.peak.toFixed(2)} %` : selected.result === undefined ? "Wird geladen …" : "Keine vollständige Prognose"}</strong></div><div className="metric"><span>Runtime Peak</span><strong>{runtime?.available ? `${runtimePeak.toFixed(2)} %` : "—"}</strong></div><div className="metric"><span>Trace Events</span><strong>{traceEvents?.toLocaleString("de-DE") ?? "—"}</strong></div></div>
            {compareRuntime?.available && <div className="impact-strip"><ResultMetric label="Δ Runtime Peak" value={`${(runtimePeak - comparePeak).toFixed(2)} %`} /><ResultMetric label="Δ Events" value={String((runtime?.summary?.event_count ?? 0) - (compareRuntime.summary?.event_count ?? 0))} /><ResultMetric label="Δ Drops" value={String((runtime?.summary?.dropped_frames ?? 0) - (compareRuntime.summary?.dropped_frames ?? 0))} /><ResultMetric label="Δ Timeouts" value={String((runtime?.summary?.timeouts ?? 0) - (compareRuntime.summary?.timeouts ?? 0))} /></div>}
            <div className="comparison-grid"><section><p className="eyebrow">Calculated</p><h3>Engineering-Prognose</h3><dl className="overview-list">
              <div><dt>Peak · Gerätenachweis</dt><dd>{forecastValue(predicted?.max_peak_load_percent,predicted?.capacity_verified,"%")}</dd></div>
              {!predicted?.capacity_verified && <div><dt>Peak · berechnete Annahme</dt><dd>{assumptions?.peak != null ? `${assumptions.peak.toFixed(2)} %` : "Keine vollständigen Annahmewerte"}</dd></div>}
              <div><dt>Worst E2E · Nachweis</dt><dd>{forecastValue(predicted?.worst_end_to_end_latency_ms,predicted?.timing_verified,"ms",3)}</dd></div>
              <div><dt>Reserve{predicted?.capacity_verified ? "" : " · berechnete Annahme"}</dt><dd>{predicted?.capacity_verified ? forecastValue(predicted.minimum_capacity_reserve_percent,true,"%") : assumptions?.reserve != null ? `${assumptions.reserve.toFixed(2)} %` : "Nachweis offen"}</dd></div><div><dt>Netze</dt><dd>{predicted ? String(predicted.network_count) : "—"}</dd></div></dl>
              <p className="runtime-chart-note">Quelle: eingefrorene Kapazitätsberechnung dieses Laufs. {predicted?.capacity_verified ? "Bestätigte Kapazitätsparameter." : "Ohne vollständige Geräte-/Parameterbelege bleibt der Nachweis offen. Nominale Last aus Busspezifikation und Nachrichten kann trotzdem unter gespeicherten Annahmen berechnet sein."} Funktionale Zeitfreigabe bleibt separat.</p>
            </section><section><p className="eyebrow">Observed</p><h3>Simulation</h3><dl className="overview-list"><div><dt>Peak / Burst</dt><dd>{runtime?.available ? `${runtimePeak.toFixed(2)} / ${runtimeBurst.toFixed(2)} %` : "—"}</dd></div><div><dt>Worst E2E</dt><dd>{runtime?.available ? `${runtimeLatency.toFixed(3)} ms` : "—"}</dd></div><div><dt>Drops / Korruption</dt><dd>{runtime?.available ? `${runtime.summary?.dropped_frames ?? 0} / ${runtime.summary?.corrupted_frames ?? 0}` : "—"}</dd></div><div><dt>Timeouts / Jitter</dt><dd>{runtime?.available ? `${runtime.summary?.timeouts ?? 0} / ${runtime.summary?.jitter_violations ?? 0}` : "—"}</dd></div></dl><p className="runtime-chart-note">Quelle: ausgeführter Simulationslauf. Der Runtime-Peak belegt die modellierte Auslastung im Peak-Fenster; er ersetzt keinen Gerätenachweis der Prognose.</p></section></div>
          </> : <div className="analysis-empty"><strong>Kein Lauf ausgewählt</strong><p>Ergebnisse werden nicht gelöscht; veraltete Läufe bleiben als historische Evidenz sichtbar.</p></div>}
        </div>
      </div>
      {selected && <div className="result-runtime-details">
        {runtime?.available ? <RuntimeAnalysis key={selected.id} projectId={projectIdForLinks} runtime={runtime} trace={observed?.model_simulation} snapshot={selected} /> : <div className="workflow-blocker warning"><strong>Keine Runtime-Metriken</strong><span>{runtime?.reason ?? "Dieser historische Lauf wurde noch ohne Runtime-Analyse erzeugt."}</span></div>}
        <div className="source-version-table"><strong>Quellversionen</strong>{Object.entries(selected.source_versions ?? {}).map(([key, value]) => <span key={key}>{key.replaceAll("_", " ")} <b>v{value}</b></span>)}</div>
      </div>}
      <div className="analysis-footer-actions"><Link className="button secondary" href={withProjectParam(selected ? `/studio/simulation?snapshot=${encodeURIComponent(selected.id)}` : "/studio/simulation", projectIdForLinks)}>Simulation öffnen</Link><Link className="button primary" href={withProjectParam("/studio/engineering", projectIdForLinks)}>Zum Engineering-Modell →</Link></div>
    </section>
  );
}

function ResultMetric({ label, value }: { label: string; value: string }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong></div>;
}

const NETWORK_COLUMNS = ["Netz", "Technologie", "Ø / Peak / Burst", "Queue Ø / Max", "Drops", "Korruption"];
const ROUTE_COLUMNS = ["Route", "Netz", "Cycle Soll / Ist", "Jitter Ø / p95 / p99", "E2E Ø / Max", "Queue Max", "Violations"];

function matchesRuntimeColumns(cells: string[], filters: string[]): boolean {
  const normalize = (value: string) => value.trim().toLocaleLowerCase("de-DE").replaceAll(",", ".");
  return filters.every((filter, index) => !filter.trim() || normalize(cells[index] ?? "").includes(normalize(filter)));
}

function runtimeRouteStatus(status: string): string {
  return status === "NOT_EVALUATED" ? "Nicht vollständig geprüft" : status === "PASS" ? "Bestanden" : "Nicht bestanden";
}

function RuntimeColumnFilters({ label, columns, filters, onChange }: {
  label: string; columns: string[]; filters: string[]; onChange: (index: number, value: string) => void;
}) {
  return <tr className="runtime-column-filters">{columns.map((column, index) => <th key={column}>
    <input type="search" aria-label={`${label}: ${column} filtern`} placeholder="Filtern …" value={filters[index] ?? ""} onChange={event => onChange(index, event.target.value)} />
  </th>)}</tr>;
}

function RuntimeAnalysis({ projectId, runtime, trace, snapshot }: { projectId?: string; runtime: RuntimeMetrics; trace?: ModelSimulationTrace; snapshot: SimulationSnapshot }) {
  const [networkFilters, setNetworkFilters] = useState<string[]>([]);
  const [networkPage, setNetworkPage] = useState(0);
  const [routeFilters, setRouteFilters] = useState<string[]>([]);
  const networkRows = useMemo(() => (runtime.networks ?? []).map(item => ({ item, cells: [
    item.network_id, item.technology,
    `${item.average_load_percent.toFixed(2)} / ${item.peak_load_percent.toFixed(2)} / ${item.burst_load_percent.toFixed(2)} %`,
    `${item.average_queue_depth.toFixed(2)} / ${item.maximum_queue_depth}`, String(item.dropped_count), String(item.corrupted_count),
  ] })), [runtime.networks]);
  const routeRows = useMemo(() => (runtime.routes ?? []).map(item => {
    const violations = `${item.timeouts} T · ${item.jitter_violations} J · ${item.latency_violations ?? 0} L · ${item.freshness_violations ?? 0} F`;
    const limits = `J ≤ ${item.jitter_limit_ms ?? "offen"} ms · L ≤ ${item.maximum_latency_limit_ms ?? "offen"} ms`;
    return { item, violations, limits, cells: [
      `${item.route_name} ${item.route_id}`, item.network_id,
      `${item.configured_cycle_ms.toFixed(3)} / ${item.actual_average_cycle_ms.toFixed(3)} ms`,
      `${item.average_jitter_ms.toFixed(3)} / ${item.p95_jitter_ms.toFixed(3)} / ${item.p99_jitter_ms.toFixed(3)} ms`,
      `${item.average_end_to_end_latency_ms.toFixed(3)} / ${item.maximum_end_to_end_latency_ms.toFixed(3)} ms`,
      `${item.maximum_queue_delay_ms.toFixed(3)} ms`, `${runtimeRouteStatus(item.status)} ${item.status} ${violations} ${limits}`,
    ] };
  }), [runtime.routes]);
  const shownNetworks = useMemo(() => networkRows.filter(row => matchesRuntimeColumns(row.cells, networkFilters)), [networkRows, networkFilters]);
  const networkEntries = simulationPage(shownNetworks, networkPage, 50);
  const shownRoutes = useMemo(() => routeRows.filter(row => matchesRuntimeColumns(row.cells, routeFilters)), [routeRows, routeFilters]);
  const chartNetworks = useMemo(() => shownNetworks.map(row => row.item), [shownNetworks]);
  const chartRoutes = useMemo(() => shownRoutes.map(row => row.item), [shownRoutes]);
  const changeNetworkFilter = (index: number, value: string) => { setNetworkPage(0); setNetworkFilters(current => NETWORK_COLUMNS.map((_, column) => column === index ? value : current[column] ?? "")); };
  const changeRouteFilter = (index: number, value: string) => setRouteFilters(current => ROUTE_COLUMNS.map((_, column) => column === index ? value : current[column] ?? ""));
  return (
    <div className="runtime-analysis">
      <div className="metric-strip compact">
        <ResultMetric label="Delivery" value={`${((runtime.reliability?.delivery_probability ?? 0) * 100).toFixed(3)} %`} />
        <ResultMetric label="Max Queue" value={String(runtime.queues?.maximum_depth ?? 0)} />
        <ResultMetric label="Queue Drops" value={String(runtime.queues?.queue_drops ?? 0)} />
        <ResultMetric label="Retries" value={String(runtime.reliability?.retransmissions ?? 0)} />
        <ResultMetric label="Clock Offset" value={`${(runtime.synchronization?.maximum_clock_offset_ms ?? 0).toFixed(3)} ms`} />
        <ResultMetric label="Peak Window" value={`${runtime.peak_window_ms ?? 0} ms`} />
        <ResultMetric label="Burst Window" value={`${runtime.burst_window_ms ?? 0} ms`} />
      </div>
      <RuntimeCharts networks={chartNetworks} routes={chartRoutes} trace={trace} snapshot={snapshot} projectId={projectId}
        peakWindowMs={runtime.peak_window_ms} filtersActive={[...networkFilters, ...routeFilters].some(filter => filter.trim())}
        onNetwork={id => { setNetworkPage(0); setNetworkFilters([id]); }} onStatus={status => setRouteFilters(ROUTE_COLUMNS.map((_, index) => index === 6 ? status : ""))}
        onReset={() => { setNetworkPage(0); setNetworkFilters([]); setRouteFilters([]); }} />
      <section className="runtime-section">
        <div className="panel-heading"><div><p className="eyebrow">Runtime networks</p><h3>Load & Queueing</h3></div><code>{runtime.calculation_model}</code></div>
        <div className="runtime-table-tools"><span role="status">{shownNetworks.length} / {networkRows.length} Netze</span><button className="button secondary tiny" type="button" disabled={!networkFilters.some(filter => filter.trim())} onClick={() => { setNetworkPage(0); setNetworkFilters([]); }}>Netzfilter zurücksetzen</button></div>
        <div className="analysis-table-wrap"><table className="analysis-table" aria-label="Runtime-Netze"><thead>
          <tr>{NETWORK_COLUMNS.map(column => <th key={column} scope="col">{column}</th>)}</tr>
          <RuntimeColumnFilters label="Runtime-Netze" columns={NETWORK_COLUMNS} filters={networkFilters} onChange={changeNetworkFilter} />
        </thead><tbody>
          {networkEntries.items.map(({ item, cells }) => <tr key={item.network_id}><td><strong>{cells[0]}</strong></td>{cells.slice(1).map((cell, index) => <td key={NETWORK_COLUMNS[index + 1]}>{cell}</td>)}</tr>)}
          {!shownNetworks.length && <tr><td colSpan={NETWORK_COLUMNS.length}>{networkRows.length ? "Keine Netze entsprechen den Spaltenfiltern." : "Keine Runtime-Netze vorhanden."}</td></tr>}
        </tbody></table></div>
        <SimulationPageControls label="Netze" {...networkEntries} onPage={setNetworkPage} />
      </section>
      <section className="runtime-section">
        <div className="panel-heading"><div><p className="eyebrow">Route drilldown</p><h3>Latency & Jitter</h3></div><Link className="button secondary tiny" href={withProjectParam("/studio/routing", projectId)}>Routing öffnen</Link></div>
        <div className="runtime-table-tools"><span role="status">{shownRoutes.length} / {routeRows.length} Routen</span><button className="button secondary tiny" type="button" disabled={!routeFilters.some(filter => filter.trim())} onClick={() => setRouteFilters([])}>Routenfilter zurücksetzen</button></div>
        <div className="analysis-table-wrap"><table className="analysis-table" aria-label="Runtime-Routen"><thead>
          <tr>{ROUTE_COLUMNS.map(column => <th key={column} scope="col">{column}</th>)}</tr>
          <RuntimeColumnFilters label="Runtime-Routen" columns={ROUTE_COLUMNS} filters={routeFilters} onChange={changeRouteFilter} />
        </thead><tbody>
          {shownRoutes.map(({ item, cells, violations, limits }) => <tr key={item.route_id}>
            <td><strong>{item.route_name}</strong><small>{item.route_id}</small></td>
            {cells.slice(1, 6).map((cell, index) => <td key={ROUTE_COLUMNS[index + 1]}>{cell}</td>)}
            <td><span className={`load-status ${item.status === "PASS" ? "load-normal" : item.status === "FAIL" ? "load-overload" : "load-warning"}`}>{runtimeRouteStatus(item.status)}</span><small>{violations}</small><small title="Verbindliche Grenzwerte aus dem eingefrorenen Routing">{limits}</small></td>
          </tr>)}
          {!shownRoutes.length && <tr><td colSpan={ROUTE_COLUMNS.length}>{routeRows.length ? "Keine Routen entsprechen den Spaltenfiltern." : "Keine Runtime-Routen vorhanden."}</td></tr>}
        </tbody></table></div>
      </section>
      {!!runtime.gateways?.length && <section className="runtime-section"><div className="panel-heading"><div><p className="eyebrow">Runtime gateways</p><h3>Throughput & Processing</h3></div></div><div className="analysis-table-wrap"><table className="analysis-table"><thead><tr><th>Gateway</th><th>Events</th><th>Throughput</th><th>Load</th><th>Queue</th><th>Processing / Conversion</th></tr></thead><tbody>{runtime.gateways.map((item) => <tr key={item.gateway_id}><td><strong>{item.gateway_id}</strong></td><td>{item.event_count}</td><td>{item.current_throughput_bps.toFixed(0)} / {item.maximum_throughput_bps.toFixed(0)} bit/s</td><td>{item.processing_load_percent.toFixed(3)} %</td><td>{item.average_queue_delay_ms.toFixed(3)} ms</td><td>{item.processing_delay_ms.toFixed(3)} / {item.protocol_conversion_delay_ms.toFixed(3)} ms</td></tr>)}</tbody></table></div></section>}
      {!!runtime.bottlenecks?.length && <div className="analysis-list findings-list">{runtime.bottlenecks.map((item) => <div className="finding finding-warning" key={`${item.type}-${item.object_id}`}><span>BOTTLENECK</span><strong>{item.type.replaceAll("_", " ")} · {item.object_id}</strong><small>{item.value.toFixed(3)} {item.unit}</small></div>)}</div>}
    </div>
  );
}

type EcuRouteGroup = { id: string; name: string; routes: RuntimeRouteMetric[]; counts: Array<number | null> };
const ECU_FAULT_COLUMNS = ["Fehlerhafte Routen", "Timeouts", "Jitter", "Latenz", "Datenalter"];
const ROUTE_STATUS_SERIES = [
  { key: "PASS", label: "Bestanden", color: "var(--accent)" },
  { key: "FAIL", label: "Nicht bestanden", color: "var(--danger)" },
  { key: "NOT_EVALUATED", label: "Nicht vollständig geprüft", color: "var(--warning)" },
];

function chartRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function validCount(value: unknown): number | null {
  return typeof value === "number" && Number.isInteger(value) && value >= 0 ? value : null;
}

function routeFaultCounts(route: RuntimeRouteMetric): Array<number | null> {
  return [route.status === "FAIL" ? 1 : route.status === "PASS" || route.status === "NOT_EVALUATED" ? 0 : null,
    validCount(route.timeouts), validCount(route.jitter_violations), validCount(route.latency_violations), validCount(route.freshness_violations)];
}

function ecuRouteGroups(configuration: SimulationSnapshot["configuration"], routes: RuntimeRouteMetric[]) {
  const parameters = chartRecord(configuration?.parameters);
  const model = chartRecord(configuration?.engineering_model ?? parameters.engineering_model);
  const rawHardware = configuration?.hardware ?? parameters.hardware;
  const hardware = chartRecord(rawHardware);
  const nodes = Array.isArray(model.nodes) && model.nodes.length ? model.nodes
    : Array.isArray(rawHardware) ? rawHardware : hardware.devices ?? hardware.nodes;
  const devices = new Map<string, { name: string; isEcu: boolean }>();
  for (const raw of Array.isArray(nodes) ? nodes : []) {
    const node = chartRecord(raw);
    if (typeof node.id !== "string" || !node.id) continue;
    const kind = node.device_type ?? node.type;
    devices.set(node.id, { name: typeof node.name === "string" && node.name ? node.name : node.id,
      isEcu: typeof kind === "string" && kind.trim().toUpperCase() === "ECU" });
  }
  const groups = new Map<string, EcuRouteGroup>();
  const seen = new Set<string>();
  let unassignedFailures = 0;
  for (const route of routes) {
    if (seen.has(route.route_id)) continue;
    seen.add(route.route_id);
    const endpoints = new Set([route.sender_id, ...(route.receiver_ids ?? [])].filter((id): id is string => !!id));
    const ecus = [...endpoints].filter(id => devices.get(id)?.isEcu);
    if (route.status === "FAIL" && !ecus.length) unassignedFailures++;
    for (const id of ecus) {
      const row = groups.get(id) ?? { id, name: devices.get(id)!.name, routes: [], counts: [0, 0, 0, 0, 0] };
      row.routes.push(route);
      const counts = routeFaultCounts(route);
      row.counts = row.counts.map((value, index) => value === null || counts[index] === null ? null : value + counts[index]!);
      groups.set(id, row);
    }
  }
  const all = [...groups.values()];
  // An incomplete aggregate must not hide a known violation on one of its routes.
  const hotspots = all.filter(row => row.routes.some(route => routeFaultCounts(route).some(value => value !== null && value > 0)))
    .sort((a, b) => (b.counts[0] ?? 0) - (a.counts[0] ?? 0)
      || b.counts.reduce<number>((sum, value) => sum + (value ?? 0), 0) - a.counts.reduce<number>((sum, value) => sum + (value ?? 0), 0)
      || a.name.localeCompare(b.name));
  return { hotspots, mappedEcus: all.length, incompleteEcus: all.filter(row => row.counts.some(value => value === null)).length,
    frozenEcus: [...devices.values()].filter(item => item.isEcu).length, unassignedFailures };
}

function RuntimeCharts({ networks, routes, trace, snapshot, projectId, peakWindowMs, filtersActive, onNetwork, onStatus, onReset }: {
  networks: RuntimeNetworkMetric[]; routes: RuntimeRouteMetric[]; trace?: ModelSimulationTrace; snapshot: SimulationSnapshot;
  projectId?: string; peakWindowMs?: number; filtersActive: boolean; onNetwork: (id: string) => void;
  onStatus: (status: string) => void; onReset: () => void;
}) {
  const [allNetworks, setAllNetworks] = useState(false);
  const [allEcus, setAllEcus] = useState(false);
  const [selectedEcu, setSelectedEcu] = useState("");
  const [expandedChart, setExpandedChart] = useState<string | null>(null);
  const chartsRef = useRef<HTMLElement>(null);
  function toggleChart(chart: string) {
    setExpandedChart(current => current === chart ? null : chart);
    chartsRef.current?.scrollIntoView({ block: "start", behavior: "instant" });
  }
  function chartButton(chart: string, name: string) {
    return <button className="button secondary tiny runtime-chart-expand" type="button" aria-expanded={expandedChart === chart}
      aria-label={`${name}: Ansicht ${expandedChart === chart ? "verkleinern" : "vergrößern"}`} onClick={() => toggleChart(chart)}>
      {expandedChart === chart ? "Ansicht verkleinern" : "Ansicht vergrößern"}</button>;
  }
  const ranked = useMemo(() => networks.filter(item => Number.isFinite(item.peak_load_percent) && item.peak_load_percent >= 0)
    .toSorted((a, b) => b.peak_load_percent - a.peak_load_percent || a.network_id.localeCompare(b.network_id)), [networks]);
  const bars = allNetworks || expandedChart === "load" ? ranked : ranked.slice(0, 8);
  const barMaximum = ranked.reduce((maximum, item) => Math.max(maximum, item.peak_load_percent), 100);
  const statuses = useMemo(() => ROUTE_STATUS_SERIES.map(series => ({ ...series, count: routes.filter(route => route.status === series.key).length })), [routes]);
  const statusTotal = statuses.reduce((sum, series) => sum + series.count, 0);
  const ecuEvidence = useMemo(() => ecuRouteGroups(snapshot.configuration, routes), [snapshot.configuration, routes]);
  const ecuRows = allEcus ? ecuEvidence.hotspots : ecuEvidence.hotspots.slice(0, 8);
  const selectedEcuRow = ecuEvidence.hotspots.find(row => row.id === selectedEcu);
  const maxima = ECU_FAULT_COLUMNS.map((_, index) => ecuEvidence.hotspots.reduce((maximum, row) => Math.max(maximum, row.counts[index] ?? 0), 1));
  let offset = 0;
  return <section className="runtime-charts" ref={chartsRef} aria-label="Diagramme des ausgewählten Simulationslaufs">
    <div className="runtime-charts-heading"><div><p className="eyebrow">Diagramme</p><h3>Last, Bewertung und Fehlerhäufung</h3>
      <p>Snapshot {snapshot.id.slice(0, 8)} · {snapshot.is_outdated ? "Historischer Lauf" : "Ausgewählter Lauf"}. Busdiagramme folgen den Netzfiltern; Routenbewertung und ECU-Häufung den Routenfiltern.</p></div>
      {filtersActive && <button type="button" className="button secondary tiny" onClick={onReset}>Tabellenfilter zurücksetzen</button>}
    </div>
    <div className={`runtime-chart-grid${expandedChart ? " runtime-chart-grid-expanded" : ""}`}>
      <section className="runtime-chart-card" hidden={expandedChart !== null && expandedChart !== "load"} aria-label="Balkendiagramm der Buslast">
        {chartButton("load", "Balkendiagramm")}
        <header><p className="eyebrow">Balken</p><h4>Peak-Buslast je Netz</h4><p>Simulationswerte in %. Peak-Fenster: {peakWindowMs == null ? "nicht dokumentiert" : `${peakWindowMs} ms`}.</p></header>
        {ranked.length ? <>
          <div className="runtime-load-bars">{bars.map(item => <button key={item.network_id} type="button" className="runtime-load-bar" onClick={() => onNetwork(item.network_id)}
            aria-label={`${item.network_name || item.network_id}: Peak ${item.peak_load_percent.toFixed(2)} Prozent; Netz filtern`}
            title={`${item.network_name || item.network_id}\n${item.network_id}\nØ ${item.average_load_percent.toFixed(2)} % · Peak ${item.peak_load_percent.toFixed(2)} % · Burst ${item.burst_load_percent.toFixed(2)} %`}>
            <span className="runtime-load-bar-label">{item.network_name || item.network_id}</span>
            <span className="runtime-load-bar-track" aria-hidden="true"><i style={{ width: `${item.peak_load_percent / barMaximum * 100}%` }} /></span>
            <strong>{item.peak_load_percent.toFixed(2)} %</strong>
          </button>)}</div>
          <div className="runtime-chart-scale"><span>Skala ab 0 %</span><span>Maximum {barMaximum.toFixed(2)} %</span></div>
          {ranked.length > 8 && expandedChart !== "load" && <button className="button secondary tiny" type="button" onClick={() => setAllNetworks(value => !value)}>{allNetworks ? "Top 8 anzeigen" : `Alle ${ranked.length} Netze anzeigen`}</button>}
          <p className="runtime-chart-note">{bars.length} von {ranked.length} Netzen mit belegtem Peak. Balken auswählen, um die Netztabelle zu filtern.</p>
        </> : <p className="runtime-chart-empty">Keine belegten Peak-Werte für die gefilterten Netze.</p>}
        {ranked.length < networks.length && <p className="runtime-chart-note">Für {networks.length - ranked.length} Netze fehlt ein gültiger Peak-Wert.</p>}
      </section>
      <section className="runtime-chart-card" hidden={expandedChart !== null && expandedChart !== "routes"} aria-label="Kreisdiagramm der Routenbewertungen">
        {chartButton("routes", "Kreisdiagramm")}
        <header><p className="eyebrow">Kreis</p><h4>Routenbewertung</h4><p>Anteile der {statusTotal} Routen mit gespeichertem Bewertungsstatus im aktuellen Filter.</p></header>
        {statusTotal ? <div className="runtime-status-chart">
          <svg viewBox="0 0 140 140" role="img" aria-label={statuses.map(series => `${series.label}: ${series.count}`).join("; ")}>
            <title>Routenbewertung des ausgewählten Laufs</title>
            {statuses.map(series => {
              const length = series.count / statusTotal * 2 * Math.PI * 48;
              const start = offset;
              offset += length;
              return <circle key={series.key} cx="70" cy="70" r="48" fill="none" stroke={series.color} strokeWidth="18"
                strokeDasharray={`${length} ${2 * Math.PI * 48}`} strokeDashoffset={-start} transform="rotate(-90 70 70)"><title>{series.label}: {series.count} ({(series.count / statusTotal * 100).toFixed(1)} %)</title></circle>;
            })}
            <text x="70" y="68" textAnchor="middle" className="runtime-chart-total">{statusTotal}</text><text x="70" y="85" textAnchor="middle" className="runtime-chart-unit">Routen</text>
          </svg>
          <div className="runtime-chart-legend">{statuses.map(series => <button key={series.key} type="button" onClick={() => onStatus(series.key)} aria-label={`${series.label}: ${series.count} Routen; Tabelle filtern`}>
            <i aria-hidden="true" style={{ background: series.color }} /><span>{series.label}</span><strong>{series.count} · {(series.count / statusTotal * 100).toFixed(1)} %</strong>
          </button>)}</div>
        </div> : <p className="runtime-chart-empty">Keine Routenbewertung für diesen Filter vorhanden.</p>}
        {statusTotal < routes.length && <p className="runtime-chart-note">Bei {routes.length - statusTotal} Routen fehlt ein bekannter Bewertungsstatus.</p>}
        <p className="runtime-chart-note">Nicht vollständig geprüfte Routen bleiben separat sichtbar. Legende auswählen, um die Routentabelle zu filtern.</p>
        <RuntimeModelViews networks={networks} routes={routes} expanded={expandedChart === "routes"}/>
      </section>
      <section className="runtime-chart-card" hidden={expandedChart !== null && expandedChart !== "trend"} aria-label="Trenddiagramm der Buslast">
        {chartButton("trend", "Trenddiagramm")}
        <header><p className="eyebrow">Trend</p><h4>Buslast im Laufverlauf</h4><p>Zeit seit Laufbeginn; ausschließlich gespeicherte Simulationspunkte.</p></header>
        <RuntimeTrendTools networks={networks} routes={routes} trace={trace} expanded={expandedChart === "trend"}/>
      </section>
      <section className="runtime-chart-card" hidden={expandedChart !== null && expandedChart !== "ecu"} aria-label="Fehlerhäufung bei ECUs">
        {chartButton("ecu", "ECU-Häufung")}
        <header><p className="eyebrow">ECU-Häufung</p><h4>Fehler auf beteiligten ECU-Routen</h4><p>Zuordnung über Hardware-IDs und ECU-Typen im eingefrorenen Modell dieses Laufs.</p></header>
        {ecuRows.length ? <>
          <div className="runtime-chart-table-scroll" tabIndex={0} aria-label="ECU-Fehlerübersicht, horizontal scrollbar"><table className="runtime-hotspot-table"><thead><tr><th scope="col">ECU</th>{ECU_FAULT_COLUMNS.map(column => <th key={column} scope="col">{column}</th>)}</tr></thead><tbody>
            {ecuRows.map(row => <tr key={row.id}><th scope="row"><button type="button" onClick={() => setSelectedEcu(current => current === row.id ? "" : row.id)} aria-pressed={selectedEcu === row.id} title={`${row.name} · ${row.id}`}>{row.name}</button></th>
              {row.counts.map((value, index) => <td key={ECU_FAULT_COLUMNS[index]} style={{ "--runtime-heat": `${value && value > 0 ? 8 + value / maxima[index] * 20 : 0}%` } as CSSProperties}
                title={value === null ? "Kennzahl für diese ECU-Routen nicht vollständig vorhanden" : `${ECU_FAULT_COLUMNS[index]}: ${value}`}>{value === null ? "—" : value}</td>)}
            </tr>)}
          </tbody></table></div>
          {ecuEvidence.hotspots.length > 8 && <button type="button" className="button secondary tiny" onClick={() => setAllEcus(value => !value)}>{allEcus ? "Top 8 anzeigen" : `Alle ${ecuEvidence.hotspots.length} betroffenen ECUs anzeigen`}</button>}
          <p className="runtime-chart-note">{ecuRows.length} von {ecuEvidence.hotspots.length} betroffenen ECUs. Farbe zeigt die Häufung je Spalte; — bedeutet fehlende Kennzahl. ECU auswählen, um ihre Routen zu sehen.</p>
        </> : <p className="runtime-chart-empty">{!ecuEvidence.frozenEcus ? "Keine ECU-Typen im eingefrorenen Modell dokumentiert." : !ecuEvidence.mappedEcus ? "Keine belegte ECU-Zuordnung zu den gefilterten Routen vorhanden." : `Auf den Routen der ${ecuEvidence.mappedEcus} zugeordneten ECUs sind keine Fehler ausgewiesen.`}</p>}
        {!!ecuEvidence.incompleteEcus && <p className="runtime-chart-note">Bei {ecuEvidence.incompleteEcus} zugeordneten ECUs sind Fehlerkennzahlen nicht vollständig vorhanden. Fehlende Werte belegen keine Fehlerfreiheit; bekannte Einzelwerte stehen in den Routendetails.</p>}
        {!!ecuEvidence.unassignedFailures && <p className="runtime-chart-note">{ecuEvidence.unassignedFailures} fehlerhafte Routen besitzen keine belegte ECU-Zuordnung und werden keiner ECU zugerechnet.</p>}
        {selectedEcuRow && <div className="runtime-hotspot-details"><strong>{selectedEcuRow.name} · {selectedEcuRow.routes.length} beteiligte Routen</strong><ul>{selectedEcuRow.routes.map(route => <li key={route.route_id}>
          <span>{route.route_name}<small>{route.route_id} · {runtimeRouteStatus(route.status)}</small><small>{routeFaultCounts(route).slice(1).map((value, index) => `${ECU_FAULT_COLUMNS[index + 1]}: ${value === null ? "—" : value}`).join(" · ")}</small></span>
          {route.canonical_route_id && <Link className="button secondary tiny" href={withProjectParam(`/studio/routing?route=${encodeURIComponent(route.canonical_route_id)}`, projectId)}>Route öffnen</Link>}
        </li>)}</ul></div>}
        <p className="runtime-chart-note">Jede Route zählt pro beteiligter ECU einmal. Eine Route kann mehrere ECUs betreffen. Dies zeigt Beteiligung, keine bewiesene Fehlerursache.</p>
      </section>
    </div>
  </section>;
}


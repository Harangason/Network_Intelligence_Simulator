"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getSimulation, listSimulations } from "@/shared/api/api";
import { mergeSimulationResult, mergeSimulationSnapshots, selectSimulationSnapshot } from "@/features/simulation/lib/simulation-result";
import type { RuntimeMetrics, SimulationJob } from "@/shared/api/types";
import {
  getWorkflowSimulationSnapshot,
  getWorkflowSnapshots,
  setWorkflowContext,
  type AnalysisSnapshot,
  type SimulationSnapshot,
} from "@/features/workflow/lib/workflow-api";
import { useWorkflowRefresh } from "@/features/workflow/lib/use-workflow-refresh";
import { readActiveProjectId, withProjectParam } from "@/features/settings/lib/user-settings";

export function ResultsWorkbench({ initialProjectId = "", initialSnapshotId }: { initialProjectId?: string; initialSnapshotId?: string }) {
  const [snapshots, setSnapshots] = useState<SimulationSnapshot[]>([]);
  const [capacity, setCapacity] = useState<AnalysisSnapshot | null>(null);
  const [jobs, setJobs] = useState<Record<string, SimulationJob>>({});
  const [selectedId, setSelectedId] = useState<string | null>(initialSnapshotId ?? null);
  const requestedSnapshot = useRef(initialSnapshotId);
  const loadSequence = useRef(0);
  const [compareId, setCompareId] = useState<string>("");
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
  const predictionSource = selected?.calculated_metrics ?? capacity?.results;
  const predicted = predictionSource && "overview" in predictionSource
    ? (predictionSource.overview as {
        max_peak_load_percent: number;
        worst_end_to_end_latency_ms: number;
        minimum_capacity_reserve_percent: number;
        capacity_verified?: boolean;
        timing_verified?: boolean;
        network_count: number;
      })
    : null;
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
          {snapshots.map((item) => <button className={selectedId === item.id ? "active" : ""} data-snapshot-id={item.id} key={item.id} onClick={() => selectRun(item.id)} type="button"><span className={`run-state run-${item.status.toLowerCase()}`}>{item.status}</span><strong>{new Date(item.created_at).toLocaleString("de-DE")}</strong><small>{item.job_id ? `Job ${item.job_id.slice(0, 10)}` : "Noch nicht ausgeführt"}</small></button>)}
          {!snapshots.length && <div className="analysis-empty"><strong>Keine Snapshots</strong><p>Nach einem erfolgreichen Preflight kann die erste Simulation gestartet werden.</p></div>}
        </aside>
        <div className="result-analysis">
          {selected ? <>
            {selected.is_outdated && <div className="workflow-blocker warning"><strong>Historisches Ergebnis · OUTDATED</strong><span>{selected.outdated_reason}</span></div>}
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
            <div className="metric-strip"><div className="metric"><span>Snapshot</span><strong>{selected.id.slice(0, 8)}</strong></div><div className="metric"><span>Ausführung</span><strong>{job?.status ?? selected.status}</strong></div><div className="metric"><span>Prognose Peak</span><strong>{predicted?.capacity_verified ? `${Number(predicted.max_peak_load_percent).toFixed(2)} %` : "Nicht nachgewiesen"}</strong></div><div className="metric"><span>Runtime Peak</span><strong>{runtime?.available ? `${runtimePeak.toFixed(2)} %` : "—"}</strong></div><div className="metric"><span>Trace Events</span><strong>{traceEvents?.toLocaleString("de-DE") ?? "—"}</strong></div></div>
            {compareRuntime?.available && <div className="impact-strip"><ResultMetric label="Δ Runtime Peak" value={`${(runtimePeak - comparePeak).toFixed(2)} %`} /><ResultMetric label="Δ Events" value={String((runtime?.summary?.event_count ?? 0) - (compareRuntime.summary?.event_count ?? 0))} /><ResultMetric label="Δ Drops" value={String((runtime?.summary?.dropped_frames ?? 0) - (compareRuntime.summary?.dropped_frames ?? 0))} /><ResultMetric label="Δ Timeouts" value={String((runtime?.summary?.timeouts ?? 0) - (compareRuntime.summary?.timeouts ?? 0))} /></div>}
            <div className="comparison-grid"><section><p className="eyebrow">Calculated</p><h3>Engineering-Prognose</h3><dl className="overview-list"><div><dt>Peak Load</dt><dd>{predicted?.capacity_verified ? `${Number(predicted.max_peak_load_percent).toFixed(2)} %` : "Nicht nachgewiesen"}</dd></div><div><dt>Worst E2E</dt><dd>{predicted?.timing_verified ? `${Number(predicted.worst_end_to_end_latency_ms).toFixed(3)} ms` : "Nicht nachgewiesen"}</dd></div><div><dt>Reserve</dt><dd>{predicted?.capacity_verified ? `${Number(predicted.minimum_capacity_reserve_percent).toFixed(2)} %` : "Nicht nachgewiesen"}</dd></div><div><dt>Netze</dt><dd>{predicted ? String(predicted.network_count) : "—"}</dd></div></dl></section><section><p className="eyebrow">Observed</p><h3>Simulation</h3><dl className="overview-list"><div><dt>Peak / Burst</dt><dd>{runtime?.available ? `${runtimePeak.toFixed(2)} / ${runtimeBurst.toFixed(2)} %` : "—"}</dd></div><div><dt>Worst E2E</dt><dd>{runtime?.available ? `${runtimeLatency.toFixed(3)} ms` : "—"}</dd></div><div><dt>Drops / Korruption</dt><dd>{runtime?.available ? `${runtime.summary?.dropped_frames ?? 0} / ${runtime.summary?.corrupted_frames ?? 0}` : "—"}</dd></div><div><dt>Timeouts / Jitter</dt><dd>{runtime?.available ? `${runtime.summary?.timeouts ?? 0} / ${runtime.summary?.jitter_violations ?? 0}` : "—"}</dd></div></dl></section></div>
            {runtime?.available ? <RuntimeAnalysis key={selected.id} projectId={projectIdForLinks} runtime={runtime} /> : <div className="workflow-blocker warning"><strong>Keine Runtime-Metriken</strong><span>{runtime?.reason ?? "Dieser historische Lauf wurde noch ohne Runtime-Analyse erzeugt."}</span></div>}
            <div className="source-version-table"><strong>Quellversionen</strong>{Object.entries(selected.source_versions ?? {}).map(([key, value]) => <span key={key}>{key.replaceAll("_", " ")} <b>v{value}</b></span>)}</div>
          </> : <div className="analysis-empty"><strong>Kein Lauf ausgewählt</strong><p>Ergebnisse werden nicht gelöscht; veraltete Läufe bleiben als historische Evidenz sichtbar.</p></div>}
        </div>
      </div>
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

function RuntimeAnalysis({ projectId, runtime }: { projectId?: string; runtime: RuntimeMetrics }) {
  const [networkFilters, setNetworkFilters] = useState<string[]>([]);
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
  const shownRoutes = useMemo(() => routeRows.filter(row => matchesRuntimeColumns(row.cells, routeFilters)), [routeRows, routeFilters]);
  const changeNetworkFilter = (index: number, value: string) => setNetworkFilters(current => NETWORK_COLUMNS.map((_, column) => column === index ? value : current[column] ?? ""));
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
      <section className="runtime-section">
        <div className="panel-heading"><div><p className="eyebrow">Runtime networks</p><h3>Load & Queueing</h3></div><code>{runtime.calculation_model}</code></div>
        <div className="runtime-table-tools"><span role="status">{shownNetworks.length} / {networkRows.length} Netze</span><button className="button secondary tiny" type="button" disabled={!networkFilters.some(filter => filter.trim())} onClick={() => setNetworkFilters([])}>Netzfilter zurücksetzen</button></div>
        <div className="analysis-table-wrap"><table className="analysis-table" aria-label="Runtime-Netze"><thead>
          <tr>{NETWORK_COLUMNS.map(column => <th key={column} scope="col">{column}</th>)}</tr>
          <RuntimeColumnFilters label="Runtime-Netze" columns={NETWORK_COLUMNS} filters={networkFilters} onChange={changeNetworkFilter} />
        </thead><tbody>
          {shownNetworks.map(({ item, cells }) => <tr key={item.network_id}><td><strong>{cells[0]}</strong></td>{cells.slice(1).map((cell, index) => <td key={NETWORK_COLUMNS[index + 1]}>{cell}</td>)}</tr>)}
          {!shownNetworks.length && <tr><td colSpan={NETWORK_COLUMNS.length}>{networkRows.length ? "Keine Netze entsprechen den Spaltenfiltern." : "Keine Runtime-Netze vorhanden."}</td></tr>}
        </tbody></table></div>
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

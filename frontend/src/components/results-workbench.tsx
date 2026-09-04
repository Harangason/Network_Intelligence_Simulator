"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getSimulation, listSimulations } from "@/lib/api";
import type { RuntimeMetrics, SimulationJob } from "@/lib/types";
import {
  getWorkflowSimulationSnapshot,
  getWorkflowSnapshots,
  setWorkflowContext,
  type AnalysisSnapshot,
  type SimulationSnapshot,
} from "@/lib/workflow-api";
import { useWorkflowRefresh } from "@/lib/use-workflow-refresh";
import { withProjectParam } from "@/lib/user-settings";

export function ResultsWorkbench({ initialProjectId = "" }: { initialProjectId?: string }) {
  const [snapshots, setSnapshots] = useState<SimulationSnapshot[]>([]);
  const [capacity, setCapacity] = useState<AnalysisSnapshot | null>(null);
  const [jobs, setJobs] = useState<Record<string, SimulationJob>>({});
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [compareId, setCompareId] = useState<string>("");
  const [error, setError] = useState("");
  const [loadedSnapshotDetails, setLoadedSnapshotDetails] = useState<Set<string>>(() => new Set());

  const load = useCallback(async () => {
    try {
      const [workflowSnapshots, simulationJobs] = await Promise.all([getWorkflowSnapshots(), listSimulations()]);
        setSnapshots((current) => workflowSnapshots.simulations.map((item) => {
          const existing = current.find((snapshot) => snapshot.id === item.id);
          return existing?.result !== undefined ? { ...item, result: existing.result } : item;
        }));
        setCapacity(workflowSnapshots.capacity);
        setJobs(Object.fromEntries(simulationJobs.map((job) => [job.id, job])));
        setSelectedId((current) => workflowSnapshots.simulations.some((item) => item.id === current)
          ? current
          : workflowSnapshots.simulations[0]?.id ?? null);
        setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Ergebnisse nicht verfügbar.");
    }
  }, []);
  useWorkflowRefresh(load);

  const selected = useMemo(() => snapshots.find((item) => item.id === selectedId) ?? null, [selectedId, snapshots]);
  const compareSnapshot = snapshots.find((item) => item.id === compareId);

  useEffect(() => {
    void setWorkflowContext({
      selected_simulation: selected ? { snapshot_id: selected.id, job_id: selected.job_id ?? null } : null,
    }).catch(() => undefined);
  }, [selected]);

  useEffect(() => {
    const ids = [selectedId, compareId].filter((value): value is string => Boolean(value));
    const missing = ids.filter((id) => {
      const snapshot = snapshots.find((item) => item.id === id);
      return snapshot && snapshot.result === undefined && !loadedSnapshotDetails.has(id);
    });
    if (!missing.length) return;
    setLoadedSnapshotDetails((current) => new Set([...current, ...missing]));
    missing.forEach((id) => {
      void getWorkflowSimulationSnapshot(id)
        .then((fullSnapshot) => {
          setSnapshots((current) => current.map((item) => item.id === fullSnapshot.id ? { ...item, ...fullSnapshot } : item));
        })
        .catch((caught) => setError(caught instanceof Error ? caught.message : "Simulationsergebnis nicht verfügbar."));
    });
  }, [compareId, loadedSnapshotDetails, selectedId, snapshots]);

  const job = selected?.job_id ? jobs[selected.job_id] : undefined;
  const observed = job?.result ?? selected?.result;
  const predictionSource = selected?.calculated_metrics ?? capacity?.results;
  const predicted = predictionSource && "overview" in predictionSource
    ? (predictionSource.overview as {
        max_peak_load_percent: number;
        worst_end_to_end_latency_ms: number;
        minimum_capacity_reserve_percent: number;
        network_count: number;
      })
    : null;
  const traceEvents = observed?.trace?.events;
  const runtime = observed?.runtime_metrics;
  const compareJob = compareSnapshot?.job_id ? jobs[compareSnapshot.job_id] : undefined;
  const compareRuntime = (compareJob?.result ?? compareSnapshot?.result)?.runtime_metrics;
  const projectIdForLinks = initialProjectId;
  const runtimePeak = Math.max(0, ...(runtime?.networks ?? []).map((item) => item.peak_load_percent));
  const runtimeBurst = Math.max(0, ...(runtime?.networks ?? []).map((item) => item.burst_load_percent));
  const runtimeLatency = Math.max(0, ...(runtime?.routes ?? []).map((item) => item.maximum_end_to_end_latency_ms));
  const comparePeak = Math.max(0, ...(compareRuntime?.networks ?? []).map((item) => item.peak_load_percent));

  async function refreshJob() {
    if (!selected?.job_id) return;
    try {
      const next = await getSimulation(selected.job_id);
      setJobs((current) => ({ ...current, [next.id]: next }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Lauf konnte nicht aktualisiert werden.");
    }
  }

  return (
    <section className="results-workbench">
      <div className="analysis-toolbar"><div><p className="eyebrow">Evidence & comparison</p><h2>Results / Analysis</h2><p>Engineering-Prognose und Simulationsergebnis bleiben mit ihren Quellversionen nachvollziehbar.</p></div><div className="analysis-actions">{snapshots.length > 1 && <label className="result-compare-select"><span>Vergleichslauf</span><select onChange={(event) => setCompareId(event.target.value)} value={compareId}><option value="">Kein Vergleich</option>{snapshots.filter((item) => item.id !== selectedId).map((item) => <option key={item.id} value={item.id}>{new Date(item.created_at).toLocaleString("de-DE")}</option>)}</select></label>}{selected?.job_id && <button className="button secondary" onClick={() => void refreshJob()} type="button">Status aktualisieren</button>}</div></div>
      {error && <div className="notice error">{error}</div>}
      <div className="results-layout">
        <aside className="result-run-list">
          <div className="result-run-list-heading"><strong>SimulationSnapshots</strong><span>{snapshots.length}</span></div>
          {snapshots.map((item) => <button className={selectedId === item.id ? "active" : ""} key={item.id} onClick={() => setSelectedId(item.id)} type="button"><span className={`run-state run-${item.status.toLowerCase()}`}>{item.status}</span><strong>{new Date(item.created_at).toLocaleString("de-DE")}</strong><small>{item.job_id ? `Job ${item.job_id.slice(0, 10)}` : "Noch nicht ausgeführt"}</small></button>)}
          {!snapshots.length && <div className="analysis-empty"><strong>Keine Snapshots</strong><p>Nach einem erfolgreichen Preflight kann die erste Simulation gestartet werden.</p></div>}
        </aside>
        <div className="result-analysis">
          {selected ? <>
            {selected.is_outdated && <div className="workflow-blocker warning"><strong>Historisches Ergebnis · OUTDATED</strong><span>{selected.outdated_reason}</span></div>}
            <div className="metric-strip"><div className="metric"><span>Snapshot</span><strong>{selected.id.slice(0, 8)}</strong></div><div className="metric"><span>Run Status</span><strong>{job?.status ?? selected.status}</strong></div><div className="metric"><span>Prognose Peak</span><strong>{predicted ? `${Number(predicted.max_peak_load_percent).toFixed(2)} %` : "—"}</strong></div><div className="metric"><span>Runtime Peak</span><strong>{runtime?.available ? `${runtimePeak.toFixed(2)} %` : "—"}</strong></div><div className="metric"><span>Trace Events</span><strong>{traceEvents?.toLocaleString("de-DE") ?? "—"}</strong></div></div>
            {compareRuntime?.available && <div className="impact-strip"><ResultMetric label="Δ Runtime Peak" value={`${(runtimePeak - comparePeak).toFixed(2)} %`} /><ResultMetric label="Δ Events" value={String((runtime?.summary?.event_count ?? 0) - (compareRuntime.summary?.event_count ?? 0))} /><ResultMetric label="Δ Drops" value={String((runtime?.summary?.dropped_frames ?? 0) - (compareRuntime.summary?.dropped_frames ?? 0))} /><ResultMetric label="Δ Timeouts" value={String((runtime?.summary?.timeouts ?? 0) - (compareRuntime.summary?.timeouts ?? 0))} /></div>}
            <div className="comparison-grid"><section><p className="eyebrow">Calculated</p><h3>Engineering-Prognose</h3><dl className="overview-list"><div><dt>Peak Load</dt><dd>{predicted ? `${Number(predicted.max_peak_load_percent).toFixed(2)} %` : "—"}</dd></div><div><dt>Worst E2E</dt><dd>{predicted ? `${Number(predicted.worst_end_to_end_latency_ms).toFixed(3)} ms` : "—"}</dd></div><div><dt>Reserve</dt><dd>{predicted ? `${Number(predicted.minimum_capacity_reserve_percent).toFixed(2)} %` : "—"}</dd></div><div><dt>Netze</dt><dd>{predicted ? String(predicted.network_count) : "—"}</dd></div></dl></section><section><p className="eyebrow">Observed</p><h3>Simulation</h3><dl className="overview-list"><div><dt>Peak / Burst</dt><dd>{runtime?.available ? `${runtimePeak.toFixed(2)} / ${runtimeBurst.toFixed(2)} %` : "—"}</dd></div><div><dt>Worst E2E</dt><dd>{runtime?.available ? `${runtimeLatency.toFixed(3)} ms` : "—"}</dd></div><div><dt>Drops / Korruption</dt><dd>{runtime?.available ? `${runtime.summary?.dropped_frames ?? 0} / ${runtime.summary?.corrupted_frames ?? 0}` : "—"}</dd></div><div><dt>Timeouts / Jitter</dt><dd>{runtime?.available ? `${runtime.summary?.timeouts ?? 0} / ${runtime.summary?.jitter_violations ?? 0}` : "—"}</dd></div></dl></section></div>
            {runtime?.available ? <RuntimeAnalysis projectId={projectIdForLinks} runtime={runtime} /> : <div className="workflow-blocker warning"><strong>Keine Runtime-Metriken</strong><span>{runtime?.reason ?? "Dieser historische Lauf wurde noch ohne Runtime-Analyse erzeugt."}</span></div>}
            <div className="source-version-table"><strong>Quellversionen</strong>{Object.entries(selected.source_versions ?? {}).map(([key, value]) => <span key={key}>{key.replaceAll("_", " ")} <b>v{value}</b></span>)}</div>
          </> : <div className="analysis-empty"><strong>Kein Lauf ausgewählt</strong><p>Ergebnisse werden nicht gelöscht; veraltete Läufe bleiben als historische Evidenz sichtbar.</p></div>}
        </div>
      </div>
      <div className="analysis-footer-actions"><Link className="button secondary" href={withProjectParam("/studio/simulation", projectIdForLinks)}>Simulation öffnen</Link><Link className="button primary" href={withProjectParam("/studio/engineering", projectIdForLinks)}>Zum Engineering-Modell →</Link></div>
    </section>
  );
}

function ResultMetric({ label, value }: { label: string; value: string }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong></div>;
}

function RuntimeAnalysis({ projectId, runtime }: { projectId?: string; runtime: RuntimeMetrics }) {
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
        <div className="analysis-table-wrap"><table className="analysis-table"><thead><tr><th>Netz</th><th>Technologie</th><th>Ø / Peak / Burst</th><th>Queue Ø / Max</th><th>Drops</th><th>Korruption</th></tr></thead><tbody>{(runtime.networks ?? []).map((item) => <tr key={item.network_id}><td><strong>{item.network_id}</strong></td><td>{item.technology}</td><td>{item.average_load_percent.toFixed(2)} / {item.peak_load_percent.toFixed(2)} / {item.burst_load_percent.toFixed(2)} %</td><td>{item.average_queue_depth.toFixed(2)} / {item.maximum_queue_depth}</td><td>{item.dropped_count}</td><td>{item.corrupted_count}</td></tr>)}</tbody></table></div>
      </section>
      <section className="runtime-section">
        <div className="panel-heading"><div><p className="eyebrow">Route drilldown</p><h3>Latency & Jitter</h3></div><Link className="button secondary tiny" href={withProjectParam("/studio/routing", projectId)}>Routing öffnen</Link></div>
        <div className="analysis-table-wrap"><table className="analysis-table"><thead><tr><th>Route</th><th>Netz</th><th>Cycle Soll / Ist</th><th>Jitter Ø / p95 / p99</th><th>E2E Ø / Max</th><th>Queue Max</th><th>Violations</th></tr></thead><tbody>{(runtime.routes ?? []).map((item) => <tr key={item.route_id}><td><strong>{item.route_name}</strong><small>{item.route_id}</small></td><td>{item.network_id}</td><td>{item.configured_cycle_ms.toFixed(3)} / {item.actual_average_cycle_ms.toFixed(3)} ms</td><td>{item.average_jitter_ms.toFixed(3)} / {item.p95_jitter_ms.toFixed(3)} / {item.p99_jitter_ms.toFixed(3)} ms</td><td>{item.average_end_to_end_latency_ms.toFixed(3)} / {item.maximum_end_to_end_latency_ms.toFixed(3)} ms</td><td>{item.maximum_queue_delay_ms.toFixed(3)} ms</td><td><span className={`load-status ${item.status === "PASS" ? "load-normal" : "load-overload"}`}>{item.timeouts} T · {item.jitter_violations} J · {item.latency_violations ?? 0} L · {item.freshness_violations ?? 0} F</span></td></tr>)}</tbody></table></div>
      </section>
      {!!runtime.gateways?.length && <section className="runtime-section"><div className="panel-heading"><div><p className="eyebrow">Runtime gateways</p><h3>Throughput & Processing</h3></div></div><div className="analysis-table-wrap"><table className="analysis-table"><thead><tr><th>Gateway</th><th>Events</th><th>Throughput</th><th>Load</th><th>Queue</th><th>Processing / Conversion</th></tr></thead><tbody>{runtime.gateways.map((item) => <tr key={item.gateway_id}><td><strong>{item.gateway_id}</strong></td><td>{item.event_count}</td><td>{item.current_throughput_bps.toFixed(0)} / {item.maximum_throughput_bps.toFixed(0)} bit/s</td><td>{item.processing_load_percent.toFixed(3)} %</td><td>{item.average_queue_delay_ms.toFixed(3)} ms</td><td>{item.processing_delay_ms.toFixed(3)} / {item.protocol_conversion_delay_ms.toFixed(3)} ms</td></tr>)}</tbody></table></div></section>}
      {!!runtime.bottlenecks?.length && <div className="analysis-list findings-list">{runtime.bottlenecks.map((item) => <div className="finding finding-warning" key={`${item.type}-${item.object_id}`}><span>BOTTLENECK</span><strong>{item.type.replaceAll("_", " ")} · {item.object_id}</strong><small>{item.value.toFixed(3)} {item.unit}</small></div>)}</div>}
    </div>
  );
}

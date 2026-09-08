"use client";
import { useEffect, useRef, useState } from "react";
import type { SimulationJob } from "@/lib/types";
import { reasoningRequest, traceFocusHref, reasoningFocusTime, type ReasoningResult } from "@/lib/reasoning-api";
import type { EngineeringProposal } from "@/lib/agent/engineering-agent";
import { EngineeringAgentEventCard } from "./engineering-agent-event";

export function ReasoningPanel({ project, jobId, jobs, start, end, focus }: {
  project: string; jobId: string | null; jobs: SimulationJob[]; start: number; end: number; focus?: number;
}) {
  const [result, setResult] = useState<ReasoningResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [golden, setGolden] = useState("");
  const [history, setHistory] = useState<{ id: string; conclusion: string; job_id: string }[]>([]);
  const [before, setBefore] = useState("");
  const [comparison, setComparison] = useState<Record<string, unknown> | null>(null);
  const [proposal, setProposal] = useState<EngineeringProposal | null>(null);
  const active = useRef<AbortController | null>(null);
  useEffect(() => {
    const controller = new AbortController(); active.current = controller;
    setResult(null); setProposal(null); setError(""); setComparison(null); setBusy(false); setBefore(""); setGolden(""); setHistory([]);
    reasoningRequest<{ items: typeof history }>(project, "", undefined, controller.signal).then(async ({ items }) => {
      if (controller.signal.aborted) return;
      setHistory(items);
      const recent = items.find(item => item.job_id === jobId);
      if (recent) {
        const data = await reasoningRequest<ReasoningResult>(project, `/${recent.id}`, undefined, controller.signal);
        if (!controller.signal.aborted) setResult(data);
      }
    }).catch(reason => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Analysen konnten nicht geladen werden."); });
    return () => active.current?.abort();
  }, [project, jobId]);
  async function perform(work: (signal: AbortSignal) => Promise<void>) {
    active.current?.abort(); const controller = new AbortController(); active.current = controller;
    setBusy(true); setError("");
    try { await work(controller.signal); }
    catch (reason) { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Ursachenanalyse fehlgeschlagen."); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  const firstTime = reasoningFocusTime(result);
  const descriptions = new Map(result?.observations.map(item => [item.id, item.description]));
  return <section className="panel trace-reasoning" aria-labelledby="reasoning-title" aria-busy={busy}>
    <h3 id="reasoning-title">Engineering-Ursachenanalyse</h3>
    <p>Python prüft das Trace-Fenster, Hypothesen und Belege. Zeitliche Nähe allein beweist keine Ursache. Änderungen bleiben Vorschläge mit menschlicher Freigabe.</p>
    {!jobId ? <p>Bitte zuerst einen gespeicherten Simulationslauf laden. Lokale Importe ohne Run-/Snapshot-Referenz liefern keine bestätigte Ursachenanalyse.</p> : <>
      <label>Golden-/Referenzlauf<select value={golden} disabled={busy} onChange={event => setGolden(event.target.value)}><option value="">Ohne Referenzlauf</option>{jobs.filter(job => job.id !== jobId && job.status === "completed").map(job => <option key={job.id} value={job.id}>{job.id}</option>)}</select></label>
      <div className="trace-storage-actions"><button className="button" type="button" disabled={busy} onClick={() => void perform(async signal => {
        const data = await reasoningRequest<ReasoningResult>(project, "", { job_id: jobId, start_s: start, end_s: end, focus_s: focus ?? null, golden_job_id: golden || null }, signal);
        if (!signal.aborted) { setResult(data); setProposal(null); setComparison(null); setHistory(items => [{ id: data.reasoning_id, conclusion: data.conclusion, job_id: jobId }, ...items]); }
      })}>Ursache analysieren</button>
      {result && <button className="button secondary" type="button" disabled={busy} onClick={() => void perform(async signal => {
        const data = await reasoningRequest<ReasoningResult>(project, `/${result.reasoning_id}`, undefined, signal); if (!signal.aborted) setResult(data);
      })}>Aktualität prüfen</button>}
      {result?.continuation && <button className="button secondary" type="button" disabled={busy || result.validation_status === "STALE"} onClick={() => void perform(async signal => {
        const data = await reasoningRequest<ReasoningResult>(project, `/${result.reasoning_id}/continue`, {}, signal); if (!signal.aborted) setResult(data);
      })}>Weitere Evidenz laden</button>}</div>
    </>}
    {busy && <p role="status">Trace-Fenster und technische Belege werden geprüft …</p>}
    {error && <p role="alert">{error}</p>}
    {result && <>
      <p role="status"><strong>{result.validation_status} · {result.completion_status}</strong></p>
      <h4>Root Cause</h4><p>{result.conclusion}</p>
      <p>Konfidenz: {(result.confidence * 100).toFixed(0)} % · regelbasierter Evidenz-Score, keine kalibrierte Wahrscheinlichkeit.</p>
      {result.validation_status === "STALE" && <p role="alert">Historischer Befund: Modell oder Laufstand geändert. Für eine Übernahme den aktuellen Simulationslauf analysieren; alte Ergebnisse bleiben nachvollziehbar.</p>}
      <details><summary>Abschlussprüfung und Konfidenz</summary><ul>{Object.entries(result.completion_checks).map(([key, value]) => <li key={key}>{value ? "✓" : "Offen:"} {key}</li>)}</ul><pre>{JSON.stringify(result.confidence_factors, null, 2)}</pre></details>
      {result.data_gaps.length > 0 && <><h4>Datenlücken / nächste Messung</h4><ul>{result.data_gaps.map(gap => <li key={gap.code}><strong>{gap.code}</strong>: {gap.message} {gap.next_measurement}</li>)}</ul></>}
      <h4>Beobachtungen</h4><ul>{result.observations.slice(0, 100).map(item => <li key={item.id}>{item.timestamp.toFixed(6)} s · {item.type}: {item.description} <a href={traceFocusHref(project, result.simulation_run_id, "trace", item.timestamp)}>Trace öffnen</a></li>)}</ul>
      {firstTime !== undefined && <nav className="trace-storage-actions" aria-label="Ursache in Trace-Ansichten fokussieren">{([['messages', 'Botschaften'], ['sequence', 'Sequenz'], ['signals', 'Signale'], ['trace', 'Trace']] as const).map(([view, title]) => <a className="button secondary" href={traceFocusHref(project, result.simulation_run_id, view, firstTime)} key={view}>{title}</a>)}</nav>}
      <h4>Kausalkette</h4>{result.causal_chain.length ? <ol>{result.causal_chain.slice(0, 50).map((link, index) => <li key={index}>{descriptions.get(link.cause) ?? link.cause} → {descriptions.get(link.effect) ?? link.effect} <strong>{link.relation}</strong></li>)}</ol> : <p>Kein belegter kausaler Pfad.</p>}
      <h4>Hypothesen / verworfene Alternativen</h4><ul>{result.hypotheses.slice(0, 100).map(item => <li key={item.id}><strong>{item.status}</strong> · {item.description}<p>{item.reason}</p></li>)}</ul>
      <details><summary>Evidence ({result.evidence_refs.length})</summary>{result.evidence_refs.slice(0, 100).map(ref => <details key={ref.id}><summary>{ref.source_type} · {ref.source_id} {ref.timestamp !== null ? `· ${ref.timestamp} s` : ""}</summary><code>{ref.id}</code><pre>{JSON.stringify(ref.details, null, 2)}</pre></details>)}</details>
      <details><summary>Source Lineage</summary><pre>{JSON.stringify(result.lineage, null, 2)}</pre></details>
      {result.comparison && <><h4>Golden Trace: erste Abweichung</h4><p>{result.comparison.first_divergence ? `${result.comparison.first_divergence.timestamp} s · ${result.comparison.first_divergence.types.join(', ')}` : "Keine Abweichung im verglichenen Fenster."}</p></>}
      <h4>Empfehlungen</h4>{result.recommended_actions.map(action => <div key={action.id}><p><strong>{action.type}</strong> · {action.description}</p>{action.proposal_supported && <button className="button secondary" type="button" disabled={busy || result.validation_status !== "CURRENT"} onClick={() => void perform(async signal => {
        const data = await reasoningRequest<EngineeringProposal>(project, `/${result.reasoning_id}/proposal`, { action_id: action.id }, signal); if (!signal.aborted) setProposal(data);
      })}>Verbesserung prüfen</button>}</div>)}
      {proposal && <EngineeringAgentEventCard event={{ type: "APPROVAL", proposal, text: proposal.rationale }} projectId={project} />}
      <h4>Re-Simulation vergleichen</h4><p>Nach freigegebener Änderung die bestehende Simulation erneut ausführen und beide Analysen vergleichen. Das Entfernen eines Faults zählt nicht als Reparatur.</p>
      <label>Vorherige Analyse<select value={before} onChange={event => setBefore(event.target.value)} disabled={busy}><option value="">Analyse auswählen</option>{history.filter(item => item.job_id !== result.simulation_run_id).map(item => <option key={item.id} value={item.id}>{item.job_id} · {item.conclusion.slice(0, 80)}</option>)}</select></label>
      <button className="button secondary" type="button" disabled={!before || busy} onClick={() => void perform(async signal => {
        const data = await reasoningRequest<Record<string, unknown>>(project, "/compare", { before_reasoning_id: before, after_reasoning_id: result.reasoning_id }, signal); if (!signal.aborted) setComparison(data);
      })}>Läufe vergleichen</button>
      {comparison && <div role="status"><strong>{String(comparison.status)}</strong><p>{String(comparison.warning)}</p><details><summary>Vergleichswerte</summary><pre>{JSON.stringify(comparison, null, 2)}</pre></details></div>}
    </>}
  </section>;
}

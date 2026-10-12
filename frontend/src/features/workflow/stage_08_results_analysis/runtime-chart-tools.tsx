"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { ModelSimulationTrace, RuntimeNetworkMetric, RuntimeRouteMetric } from "@/shared/api/types";
import { simulationPage } from "@/features/simulation/lib/simulation-pagination";
import { SimulationPageControls } from "@/features/simulation/ui/simulation-page-controls";
import { CHART_COLORS, extremaSample, jitterAssessment, loadWindow, zoomWindow } from "./runtime-chart-data";

export function RuntimeTrendTools({ networks, routes, trace, expanded }: {
  networks: RuntimeNetworkMetric[]; routes: RuntimeRouteMetric[]; trace?: ModelSimulationTrace; expanded: boolean;
}) {
  const points = trace?.bus_load ?? [];
  const choices = useMemo(() => {
    const ids = new Set(points.map(p => p.network_id));
    return networks.filter(n => ids.has(n.network_id)).toSorted((a,b) => (a.network_name || a.network_id).localeCompare(b.network_name || b.network_id));
  }, [points, networks]);
  const [selection, setSelection] = useState<string[] | null>(null);
  const ids = (selection ?? choices.slice(0, 1).map(n => n.network_id)).filter(id => choices.some(n => n.network_id === id));
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState("line");
  const [autoScale, setAutoScale] = useState(true);
  const [range, setRange] = useState<readonly [number,number] | null>(null);
  const [page, setPage] = useState(0);
  const plot = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(560);
  useEffect(() => {
    if (!plot.current) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(440, Math.round(entry.contentRect.width))));
    observer.observe(plot.current);
    return () => observer.disconnect();
  }, []);
  const all = useMemo(() => loadWindow(points, ids, 0, Infinity), [points, ids.join("|")]);
  const total = all.reduce((max,p) => Math.max(max,p.time_s),.001);
  const start = Math.max(0, Math.min(range?.[0] ?? 0, total - total / 100));
  const end = Math.max(start + total / 100, Math.min(range?.[1] ?? total, total));
  const visible = useMemo(() => loadWindow(all, ids, start, end), [all, ids.join("|"), start, end]);
  const series = ids.map((id, index) => ({ id, color: CHART_COLORS[index], network: choices.find(n => n.network_id === id),
    points: extremaSample(visible.filter(p => p.network_id === id)) }));
  const rawPage = simulationPage(visible, page, 100);
  const maximumLoad = visible.reduce((max,p) => Math.max(max,p.load_percent),autoScale ? .1 : 100) * (autoScale ? 1.1 : 1);
  const height = expanded ? 420 : 260, left = 64, right = 24, top = 26, bottom = 36;
  const x = (time:number) => left + (time-start) / (end-start) * (width-left-right);
  const y = (load:number) => top + (1-load/maximumLoad) * (height-top-bottom);
  function updateRange(next: readonly [number,number] | null) { setRange(next); setPage(0); }
  function toggle(id: string) { setSelection(ids.includes(id) ? ids.filter(i => i !== id) : [...ids, id].slice(0,6)); setPage(0); }
  function pan(direction:number) {
    const span = end-start, next = Math.max(0,Math.min(total-span,start+span*.5*direction));
    updateRange([next,next+span]);
  }
  return <div className="runtime-trend-tools">
    <div className="runtime-plot-toolbar">
      <label>Diagrammtyp<select aria-label="Diagrammtyp" value={kind} onChange={e => setKind(e.target.value)}><option value="line">Linien</option><option value="step">Stufen</option><option value="points">Punkte</option><option value="bar">Balken</option></select></label>
      <label>Y-Skala<select aria-label="Y-Skala" value={autoScale ? "auto" : "full"} onChange={e => setAutoScale(e.target.value === "auto")}><option value="auto">An sichtbare Werte anpassen</option><option value="full">Ab 0 bis mindestens 100 %</option></select></label>
      <div className="runtime-zoom-buttons"><button className="button secondary tiny" disabled={!all.length} onClick={() => updateRange(zoomWindow(start,end,total,.5))}>Zoom +</button><button className="button secondary tiny" disabled={!all.length} onClick={() => updateRange(zoomWindow(start,end,total,2))}>Zoom −</button><button className="button secondary tiny" disabled={start <= 0} onClick={() => pan(-1)} aria-label="Zeitfenster nach links">←</button><button className="button secondary tiny" disabled={end >= total} onClick={() => pan(1)} aria-label="Zeitfenster nach rechts">→</button><button className="button secondary tiny" onClick={() => updateRange(null)}>Zoom zurücksetzen</button></div>
    </div>
    <details className="runtime-network-picker"><summary>Netze überlagern · {ids.length} / 6 ausgewählt</summary>
      <label>Netze suchen<input type="search" value={search} onChange={e => setSearch(e.target.value)} placeholder="Name oder Bustyp" /></label>
      <p className="runtime-chart-note">Bis zu sechs Netze beliebiger Bustypen. Jede Kurve behält ihre eigenen Zeitpunkte und Auswertefenster.</p>
      <div>{choices.filter(n => `${n.network_name} ${n.network_id} ${n.technology}`.toLowerCase().includes(search.toLowerCase())).map(n => <label key={n.network_id}><input type="checkbox" checked={ids.includes(n.network_id)} disabled={!ids.includes(n.network_id) && ids.length >= 6} onChange={() => toggle(n.network_id)} />{n.network_name || n.network_id}<small>{n.technology}</small></label>)}</div>
    </details>
    <div className="runtime-series-legend">{series.map(s => <span key={s.id}><i style={{background:s.color}} />{s.network?.network_name || s.id} · {s.network?.technology} · Fenster {[...new Set(all.filter(p => p.network_id === s.id).map(p => p.window_ms))].map(w => Number.isFinite(w) ? `${w} ms` : "offen").join(" / ")}</span>)}</div>
    <div className="runtime-trend-scroll" ref={plot}>
      {visible.length ? <svg viewBox={`0 0 ${width} ${height}`} style={{height}} role="img" aria-label={`Buslastverlauf: ${ids.length} Netze, ${start.toFixed(3)} bis ${end.toFixed(3)} Sekunden; Buslast in Prozent`}>
        <title>Gespeicherte Buslastwerte · {kind === "step" ? "Stufendarstellung" : kind === "bar" ? "Balkendarstellung" : kind === "points" ? "Punktdarstellung" : "Linienverbindung"}</title>
        {[0,maximumLoad/2,maximumLoad].map(v => <g key={v}><line x1={left} x2={width-right} y1={y(v)} y2={y(v)} className="runtime-trend-grid"/><text x={left-8} y={y(v)+4} textAnchor="end">{v.toFixed(2)}</text></g>)}
        <line x1={left} x2={left} y1={top} y2={height-bottom} className="runtime-trend-axis"/><line x1={left} x2={width-right} y1={height-bottom} y2={height-bottom} className="runtime-trend-axis"/>
        {[start,(start+end)/2,end].map(v => <text key={v} x={x(v)} y={height-12} textAnchor="middle">{v.toFixed(3)} s</text>)}<text x={left} y={16}>Buslast (%)</text>
        {series.map(s => <g key={s.id}>
          {kind === "line" && s.points.length > 1 && <polyline fill="none" stroke={s.color} strokeWidth="2" points={s.points.map(p => `${x(p.time_s)},${y(p.load_percent)}`).join(" ")}/>}
          {kind === "step" && s.points.length > 1 && <path fill="none" stroke={s.color} strokeWidth="2" d={s.points.map((p,i) => i === 0 ? `M${x(p.time_s)},${y(p.load_percent)}` : `H${x(p.time_s)}V${y(p.load_percent)}`).join(" ")}/>}
          {s.points.map((p,i) => kind === "bar" ? <line key={i} x1={x(p.time_s)} x2={x(p.time_s)} y1={y(0)} y2={y(p.load_percent)} stroke={s.color} strokeWidth={4} opacity=".7"><title>{s.network?.network_name} · {p.time_s.toFixed(3)} s · {p.load_percent.toFixed(2)} %</title></line> : <circle key={i} cx={x(p.time_s)} cy={y(p.load_percent)} r="3" fill={s.color}><title>{s.network?.network_name} · {p.time_s.toFixed(3)} s · {p.load_percent.toFixed(2)} % · Fenster {p.window_ms} ms</title></circle>)}
        </g>)}
      </svg> : <p className="runtime-chart-empty">Keine gespeicherten Buslastpunkte im gewählten Netz-/Zeitfilter.</p>}
    </div>
    {!!all.length && <label className="runtime-time-window">Zeitfenster verschieben · {start.toFixed(3)}–{end.toFixed(3)} s<input aria-label="Zeitfenster verschieben" type="range" min={0} max={Math.max(0,total-(end-start))} step={total/1000} value={start} disabled={end-start >= total} onChange={e => updateRange([Number(e.target.value),Number(e.target.value)+end-start])}/></label>}
    <p className="runtime-chart-note">{visible.length} von {all.length} gespeicherten Punkten im Zeitfenster. Verbindungen zwischen Punkten sind Darstellung, keine zusätzlichen Messungen.{series.some(s => s.points.length < visible.filter(p => p.network_id === s.id).length) ? " Kurvenauszug erhält echte Minima, Maxima und Endpunkte; alle Werte stehen in der Tabelle." : ""}</p>
    <details className="runtime-trend-values"><summary>Werte als Tabelle</summary><SimulationPageControls label="Buslastwerte" {...rawPage} onPage={setPage}/><div className="runtime-chart-table-scroll"><table><thead><tr><th>Netz</th><th>Zeit (s)</th><th>Buslast (%)</th><th>Fenster (ms)</th></tr></thead><tbody>{rawPage.items.map((p,i) => <tr key={i}><td>{choices.find(n => n.network_id === p.network_id)?.network_name || p.network_id}</td><td>{p.time_s.toFixed(3)}</td><td>{p.load_percent.toFixed(2)}</td><td>{Number.isFinite(p.window_ms) ? p.window_ms : "—"}</td></tr>)}</tbody></table></div></details>
    <PartnerJitter routes={routes.filter(r => ids.includes(r.network_id))}/>
  </div>;
}

function PartnerJitter({ routes }: { routes:RuntimeRouteMetric[] }) {
  const [sender,setSender] = useState("");
  const [receiver,setReceiver] = useState("");
  const [page,setPage] = useState(0);
  const senders = new Map(routes.filter(r => r.sender_id).map(r => [r.sender_id!,r.sender || r.sender_id!]));
  const receivers = new Map(routes.flatMap(r => (r.receiver_ids ?? []).map((id,i) => [id,r.receivers?.[i] || id] as const)));
  const filtered = routes.filter(r => (!sender || sender === r.sender_id) && (!receiver || r.receiver_ids?.includes(receiver)))
    .toSorted((a,b) => b.maximum_jitter_ms-a.maximum_jitter_ms);
  const entries = simulationPage(filtered,page,10);
  const scale = Math.max(.001,...filtered.map(r => Number.isFinite(r.maximum_jitter_ms) ? r.maximum_jitter_ms : 0),...filtered.map(r => r.jitter_limit_ms ?? 0).filter(Number.isFinite));
  const display = (v:unknown) => typeof v === "number" && Number.isFinite(v) ? v.toFixed(3) : "—";
  return <section className="runtime-partner-jitter" aria-label="Jitter zwischen Kommunikationspartnern"><header><h4>Jitter zwischen Kommunikationspartnern</h4><p>Gesamter Lauf, unabhängig vom Zoom-Zeitfenster. Gespeicherte Routenmetriken der gewählten Netze: |Ist-Intervall − Soll-Zyklus| in ms. Keine Geräte- oder funktionale Zeitfreigabe.</p></header>
    <div className="runtime-plot-toolbar"><label>Sender<select aria-label="Sender" value={sender} onChange={e => {setSender(e.target.value);setPage(0);}}><option value="">Alle Sender</option>{[...senders].map(([id,name]) => <option key={id} value={id}>{name}</option>)}</select></label><label>Empfänger<select aria-label="Empfänger" value={receiver} onChange={e => {setReceiver(e.target.value);setPage(0);}}><option value="">Alle Empfänger</option>{[...receivers].map(([id,name]) => <option key={id} value={id}>{name}</option>)}</select></label></div>
    <SimulationPageControls label="Jitter-Routen" {...entries} onPage={setPage}/>
    <div className="runtime-chart-table-scroll"><table className="runtime-jitter-table"><thead><tr><th>Sender → Empfänger / Route</th><th>Jitter Ø / p95 / p99 (ms)</th><th>Max / Grenze (ms)</th><th>Bewertung</th></tr></thead><tbody>{entries.items.map(r => {
      const status=jitterAssessment(r), measured=status !== "Keine bewertbaren Intervalle";
      return <tr key={r.route_id}><th scope="row">{r.sender || r.sender_id || "Sender offen"} → {r.receivers?.join(", ") || r.receiver_ids?.join(", ") || "Empfänger offen"}<small>{r.route_name || r.route_id}</small></th><td>{measured ? `${display(r.average_jitter_ms)} / ${display(r.p95_jitter_ms)} / ${display(r.p99_jitter_ms)}` : "—"}</td><td>{measured ? display(r.maximum_jitter_ms) : "—"} / {display(r.jitter_limit_ms)}<span className="runtime-jitter-track">{measured && <i style={{width:`${r.maximum_jitter_ms/scale*100}%`}}/>}{r.jitter_limit_ms != null && Number.isFinite(r.jitter_limit_ms) && r.jitter_limit_ms >= 0 && <b style={{left:`${r.jitter_limit_ms/scale*100}%`}} title="Jitter-Grenze"/>}</span></td><td>{status}</td></tr>;
    })}</tbody></table></div>
    {!filtered.length && <p className="runtime-chart-empty">Keine Routen für diese Partnerauswahl vorhanden.</p>}
    <p className="runtime-chart-note">Balken: maximaler Jitter · Strich: explizite Grenze. Weniger als zwei gültige Empfangsereignisse oder ein fehlender Soll-Zyklus ergeben keine Bewertung. Ohne Grenze ist auch 0 ms kein bestandener Nachweis. Mehrere Empfänger bleiben als gemeinsame Route sichtbar.</p>
  </section>;
}

export function RuntimeModelViews({networks,routes,expanded}: {networks:RuntimeNetworkMetric[];routes:RuntimeRouteMetric[];expanded:boolean}) {
  const [view,setView] = useState("technology");
  const [page,setPage] = useState(0);
  const grouped = new Map<string,{name:string,count:number}>();
  function add(id:string,name:string) { const old=grouped.get(id); grouped.set(id,{name,count:(old?.count ?? 0)+1}); }
  if (view === "technology") networks.forEach(n => add(n.technology || "unknown", n.technology || "Technologie offen"));
  if (view === "network") routes.forEach(r => add(r.network_id,networks.find(n => n.network_id === r.network_id)?.network_name || r.network_id));
  if (view === "partners") routes.forEach(r => {
    if (!(r.receiver_ids?.length)) add(`${r.sender_id ?? "unknown"}|unknown`,`${r.sender || r.sender_id || "Sender offen"} → Empfänger offen`);
    else r.receiver_ids.forEach((id,i) => add(`${r.sender_id ?? "unknown"}|${id}`,`${r.sender || r.sender_id || "Sender offen"} → ${r.receivers?.[i] || id}`));
  });
  const ranked=[...grouped].map(([id,row]) => ({id,...row})).toSorted((a,b)=>b.count-a.count || a.name.localeCompare(b.name));
  const entries=simulationPage(ranked,page,expanded?24:8),maximum=Math.max(1,...ranked.map(r=>r.count));
  return <section className="runtime-model-views" aria-label="Weitere Modellsichten"><label>Modellsicht<select aria-label="Modellsicht" value={view} onChange={e=>{setView(e.target.value);setPage(0);}}><option value="technology">Netze je Bustyp</option><option value="network">Routen je Netz</option><option value="partners">Routen zwischen Partnern</option></select></label>
    <div className="runtime-model-bars">{entries.items.map(r=><div key={r.id}><span title={r.name}>{r.name}</span><i style={{width:`${r.count/maximum*100}%`}}/><strong>{r.count}</strong></div>)}</div>
    <SimulationPageControls label="Modellsicht" {...entries} onPage={setPage}/>
    <p className="runtime-chart-note">Gespeicherter Lauf im aktuellen Tabellenfilter · {view === "technology" ? `${networks.length} Netze` : `${routes.length} Routen`}. {view === "partners" ? "Eine Multicast-Route zählt je Empfänger einmal; Beteiligung ist keine zusätzliche physische Übertragung." : "Anzahl, keine zusätzliche Lastberechnung."}</p>
    {!ranked.length && <p className="runtime-chart-empty">Keine Daten im aktuellen Filter.</p>}
  </section>;
}

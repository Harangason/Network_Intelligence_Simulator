'use client';
import { useEffect, useMemo, useState } from 'react';
import type { SimulationJob } from '@/shared/api/types';
import { eventFromRecord, traceEventFindings, type TraceEvent } from '../lib/trace-records';
import { readTraceWindow } from '../lib/trace-window-reader';
import type { AnalysisContext, CompareSide } from '../lib/analysis-workspace';
import type { WorkspaceStore } from '../lib/analysis-workspace-browser';
import { simulationPage } from '@/features/simulation/lib/simulation-pagination';
import { SimulationPageControls } from '@/features/simulation/ui/simulation-page-controls';
export function AnalysisCompare({context,store,jobs}: {context:AnalysisContext;store:WorkspaceStore;jobs:SimulationJob[]}) {
  const initial: CompareSide = {run_id:context.simulation_run_id,trace_id:context.trace_id,object_id:null,time_range:context.time_range,view:'trace'};
  const [left,setLeft] = useState<CompareSide>(() => context.compare_left ?? initial);
  const [right,setRight] = useState<CompareSide>(() => context.compare_right ?? {...initial,run_id:null,trace_id:null});
  const [leftEvents,setLeftEvents] = useState<TraceEvent[]>([]), [rightEvents,setRightEvents] = useState<TraceEvent[]>([]);
  const [error,setError] = useState(''), [loading,setLoading] = useState(false), [page,setPage] = useState(0);
  const [counts,setCounts] = useState<[boolean,boolean]>([false,false]);
  useEffect(() => {
    let active=true; setLoading(true); setError(''); setLeftEvents([]); setRightEvents([]); setPage(0);
    const read = async (side:CompareSide) => {
      const source = side.trace_id ?? side.run_id;
      if (!source) return {events:[],next_cursor:null};
      return readTraceWindow(context.project_id,source,new URLSearchParams({cursor:'0',limit:'400',start_s:String(side.time_range[0]),end_s:String(side.time_range[1]),q:''}));
    };
    const timer=window.setTimeout(() => { void Promise.all([read(left),read(right)]).then(([a,b]) => {
      if (!active) return;
      const scoped=(events:Record<string,unknown>[],side:CompareSide) => events.map(eventFromRecord).filter(e => !side.object_id || e.refs.some(ref => ref.id === side.object_id) || e.signals.some(signal => signal.id === side.object_id) || e.original.message_id === side.object_id || e.original.network_id === side.object_id);
      setLeftEvents(scoped(a.events,left));setRightEvents(scoped(b.events,right));setCounts([a.next_cursor != null,b.next_cursor != null]);
    }).catch(e => {if(active)setError(e instanceof Error ? e.message:'Vergleich nicht verfügbar.');}).finally(() => {if(active)setLoading(false);}); },200);
    return () => {active=false;window.clearTimeout(timer);};
  },[context.project_id,left,right]);
  const rows = useMemo(() => {
    const groups = (events:TraceEvent[]) => {
      const result = new Map<string,{label:string;count:number;findings:number;values:Set<string>}>();
      for(const e of events) {
        const key=String(e.original.message_ids ?? e.original.message_id ?? e.message)+'|'+String(e.original.network_id ?? e.original.network ?? e.technology);
        const v=result.get(key) ?? {label:`${e.message} · ${e.technology}`,count:0,findings:0,values:new Set<string>()};
        v.count++; v.findings+=traceEventFindings(e).length; for(const s of e.signals)v.values.add(`${s.name}: ${s.value ?? '—'} ${s.unit}`); result.set(key,v);
      } return result;
    };
    const a=groups(leftEvents), b=groups(rightEvents);
    return [...new Set([...a.keys(),...b.keys()])].map(key => {const x=a.get(key),y=b.get(key);const av=[...(x?.values ?? [])].sort().join(' · '),bv=[...(y?.values ?? [])].sort().join(' · ');return {key,label:x?.label ?? y!.label,left:x?.count ?? 0,right:y?.count ?? 0,leftFindings:x?.findings ?? 0,rightFindings:y?.findings ?? 0,leftValues:av,rightValues:bv,different:x?.count !== y?.count || x?.findings !== y?.findings || av !== bv};});
  },[leftEvents,rightEvents]);
  const shown=simulationPage(rows,page,50);
  function update(side:'left'|'right',next:CompareSide) {if(side==='left')setLeft(next);else setRight(next);store.update(side==='left'?{compare_left:next}:{compare_right:next});const p=new URLSearchParams(window.location.search);p.set('compare_left',JSON.stringify(side==='left'?next:left));p.set('compare_right',JSON.stringify(side==='right'?next:right));window.history.replaceState(window.history.state,'',`${window.location.pathname}?${p}${window.location.hash}`);}
  return <section className="panel analysis-compare" aria-label="Analysevergleich">
    <header><span className="eyebrow">Vergleich · getrennte Referenzen</span><h3>Golden / Fault · Erwartet / Beobachtet</h3></header>
    <div className="analysis-compare-sides">{([['left',left],['right',right]] as const).map(([side,v]) => <fieldset key={side}><legend>{side==='left'?'Referenz / Golden':'Vergleich / Fault'}</legend><label>Lauf<select aria-label={`${side==='left'?'Linker':'Rechter'} Vergleichslauf`} value={v.run_id ?? ''} onChange={e => update(side,{...v,run_id:e.target.value||null,trace_id:e.target.value||null})}><option value="">Lauf auswählen</option>{jobs.filter(j=>j.status==='completed'&&!j.validate_only).map(j=><option value={j.id} key={j.id}>{j.result?.model_simulation?.scenario.mode ?? 'Simulation'} · {j.created_at} · {j.id.slice(0,8)}</option>)}</select></label><label>Trace-Import / Laufreferenz<input maxLength={200} value={v.trace_id ?? ''} placeholder="import:Session-ID oder Lauf-ID" onChange={e=>update(side,{...v,trace_id:e.target.value||null})} /></label><label>Objektfilter<input maxLength={200} value={v.object_id ?? ''} placeholder="ECU-, Signal- oder Nachrichtenreferenz" onChange={e=>update(side,{...v,object_id:e.target.value||null})} /></label><div className="trace-time-row"><label>Von (s)<input type="number" min="0" max={v.time_range[1]} step="any" value={v.time_range[0]} onChange={e=>{const n=e.target.valueAsNumber;if(Number.isFinite(n)&&n>=0&&n<=v.time_range[1])update(side,{...v,time_range:[n,v.time_range[1]]});}} /></label><label>Bis (s)<input type="number" min={v.time_range[0]} max="1000000000000000" step="any" value={v.time_range[1]===1e15?'':v.time_range[1]} placeholder="Ende" onChange={e=>{const n=e.target.value===''?1e15:e.target.valueAsNumber;if(Number.isFinite(n)&&n>=v.time_range[0])update(side,{...v,time_range:[v.time_range[0],n]});}} /></label></div></fieldset>)}</div>
    <p>Verglichen werden Originaldaten in zwei getrennten Zeitfenstern, höchstens 400 Ereignisse je Seite. Keine automatische zeitliche Ausrichtung, keine Aussage über funktionale Akzeptanz. Objektfilter sind explizite Modellreferenzen.</p>
    <p role="status">{loading?'Vergleichsfenster werden geladen …':`${leftEvents.length} links · ${rightEvents.length} rechts · ${rows.filter(r=>r.different).length} Gruppen mit Abweichung`}{counts.some(Boolean)?' · Weitere Ereignisse außerhalb dieses Ausschnitts vorhanden.':''}</p>
    {error && <p className="notice error" role="alert">{error}</p>}
    <SimulationPageControls label="Vergleichsgruppen" {...shown} onPage={setPage}/>
    <div className="trace-table-scroll"><table><thead><tr><th>Nachricht / Netz</th><th>Ereignisse links / rechts</th><th>Befunde links / rechts</th><th>Signalwerte links</th><th>Signalwerte rechts</th><th>Vergleich</th></tr></thead><tbody>{shown.items.map(r=><tr key={r.key} className={r.different?'analysis-difference':''}><td>{r.label}</td><td>{r.left} / {r.right}</td><td>{r.leftFindings} / {r.rightFindings}</td><td>{r.leftValues||'—'}</td><td>{r.rightValues||'—'}</td><td>{r.different?'Abweichung im Ausschnitt':'Gleiche Aggregation im Ausschnitt'}</td></tr>)}</tbody></table></div>
  </section>;
}

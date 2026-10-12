import {analysisWindowId} from './analysis-workspace';
type TraceWindow = { events: Record<string,unknown>[]; sequence_model?: unknown; [key:string]:unknown };
let worker: SharedWorker | null = null;
let unavailable = false;
const pending = new Map<string,{resolve:(result:TraceWindow)=>void;reject:(error:Error)=>void;timer:number}>();
function sharedReader() {
  if (unavailable || typeof SharedWorker === 'undefined') return null;
  if (!worker) {
    try {
      worker = new SharedWorker('/nis-analysis-worker.js',{name:'nis-analysis-v1'});
      worker.port.onmessage = event => { const task = pending.get(event.data?.id); if (!task) return; pending.delete(event.data.id); clearTimeout(task.timer); if (event.data.error) task.reject(new Error(event.data.error)); else task.resolve(event.data.result); };
      worker.onerror = () => { unavailable=true; for (const task of pending.values()) { clearTimeout(task.timer); task.reject(new Error('Gemeinsamer Trace-Lesedienst nicht verfügbar. Bitte erneut laden.')); } pending.clear(); worker=null; };
      worker.port.start();
      window.addEventListener('nis:analysis-session-ended',() => worker?.port.postMessage({type:'CLEAR'}));
    } catch { unavailable=true; return null; }
  }
  return worker;
}
/** The same project-scoped range endpoint in worker-capable and fallback browsers. */
export async function readTraceWindow(project: string, source: string, parameters: URLSearchParams): Promise<TraceWindow> {
  const reader = sharedReader();
  if (reader) return new Promise((resolve,reject) => {
    const id = analysisWindowId();
    const timer = window.setTimeout(() => { pending.delete(id); reject(new Error('Trace-Zeitfenster konnte innerhalb des Zeitlimits nicht geladen werden.')); },20000);
    pending.set(id,{resolve,reject,timer}); reader.port.postMessage({type:'READ',id,project,source,parameters:parameters.toString()});
  });
  const endpoint = source.startsWith('import:') ? `/api/trace-import/${encodeURIComponent(source.slice(7))}` : `/api/simulations/${encodeURIComponent(source)}/trace-window`;
  const response = await fetch(`${endpoint}?${parameters}`,{headers:{'X-Project-ID':project},credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(15000)});
  const result = await response.json(); if (!response.ok) throw Error(result.error ?? `Trace-Abruf fehlgeschlagen (${response.status}).`);
  return result;
}

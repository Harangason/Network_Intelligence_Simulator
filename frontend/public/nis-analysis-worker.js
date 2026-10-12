/* Bounded read cache shared by windows. No technical writes and no durable trace copy. */
const entries = new Map();
const MAX_BYTES = 16 * 1024 * 1024;
let bytes = 0;
let generation = 0;
function endpoint(project, source, parameters) {
  if (typeof project !== 'string' || project.length > 200 || typeof source !== 'string' || source.length > 200) throw Error('Ungültiger Analysekontext.');
  const p = new URLSearchParams(parameters);
  const limit = Number(p.get('limit')), start = Number(p.get('start_s')), end = Number(p.get('end_s')), cursor = Number(p.get('cursor'));
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > 2000 || !Number.isSafeInteger(cursor) || cursor < 0 || !Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end < start || end > 1e15 || (p.get('q') ?? '').length > 4096) throw Error('Ungültiges Trace-Fenster.');
  return source.startsWith('import:') ? `/api/trace-import/${encodeURIComponent(source.slice(7))}?${p}` : `/api/simulations/${encodeURIComponent(source)}/trace-window?${p}`;
}
async function read(project, source, parameters) {
  const readGeneration = generation;
  const path = endpoint(project,source,parameters);
  const options = { headers:{'X-Project-ID':project}, credentials:'same-origin', cache:'no-store', signal:AbortSignal.timeout(15000) };
  // Cache hits still require the existing server-side project/source access check.
  const access = await fetch(source.startsWith('import:') ? `/api/trace-import/${encodeURIComponent(source.slice(7))}?cursor=0&limit=1&start_s=0&end_s=1000000000000000` : `/api/simulations/${encodeURIComponent(source)}?view=metadata`, options);
  if (!access.ok) { const entry=entries.get(`${project}:${path}`); if(entry)bytes-=entry.bytes; entries.delete(`${project}:${path}`); throw Error(`Analysezugriff nicht bestätigt (${access.status}).`); }
  const key = `${project}:${path}`, cached = entries.get(key);
  if (cached && Date.now()-cached.at < 3000) return cached.request;
  if (cached) { bytes -= cached.bytes; entries.delete(key); }
  const entry = { at:Date.now(), bytes:0, request:null };
  entry.request = (async () => {
    const response = await fetch(path,{...options,signal:AbortSignal.timeout(15000)});
    const text = await response.text();
    if (!response.ok) throw Error(`Trace-Abruf fehlgeschlagen (${response.status}).`);
    const result = JSON.parse(text);
    if (!Array.isArray(result.events) || result.events.length > 2000) throw Error('Ungültige Trace-Antwort.');
    if (readGeneration !== generation) throw Error('Analysesitzung wurde beendet.');
    if (entries.get(key) === entry) {
      entry.bytes = text.length*2; bytes += entry.bytes;
      while (entries.size && (entries.size > 8 || bytes > MAX_BYTES)) { const [oldKey,old] = entries.entries().next().value; bytes -= old.bytes; entries.delete(oldKey); }
    }
    return result;
  })().catch(error => { if (entries.get(key) === entry) { bytes -= entry.bytes; entries.delete(key); } throw error; });
  entries.set(key,entry); return entry.request;
}
self.onconnect = event => {
  const port = event.ports[0];
  port.onmessage = async event => {
    const p = event.data;
    if (p?.type === 'CLEAR') { generation++; entries.clear(); bytes=0; return; }
    if (p?.type !== 'READ' || typeof p.id !== 'string') return;
    const start=generation;
    try { const result=await read(p.project,p.source,p.parameters); if(start!==generation)throw Error('Analysesitzung wurde beendet.'); port.postMessage({id:p.id,result}); }
    catch (error) { port.postMessage({id:p.id,error:error instanceof Error ? error.message:'Trace-Abruf fehlgeschlagen.'}); }
  };
  port.start();
};

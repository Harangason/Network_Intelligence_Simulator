'use client';
import { useEffect, useState } from 'react';
import { readActiveProjectId } from '@/features/settings/lib/user-settings';
import { analysisWorkspaceStore, type WorkspaceState, type WorkspaceStore } from '../lib/analysis-workspace-browser';
import { ANALYSIS_VIEWS, analysisWindowId, analysisViewHref, type AnalysisView, type LinkMode, type WorkspaceProfile } from '../lib/analysis-workspace';
export function useAnalysisWorkspace(project?: string) {
  const [connection,setConnection] = useState<{state:WorkspaceState;store:WorkspaceStore}|null>(null);
  useEffect(() => {
    const store = analysisWorkspaceStore(project || readActiveProjectId());
    const update = () => setConnection({store,state:store.snapshot()});
    update(); return store.subscribe(update);
  },[project]);
  return connection;
}
const PRESETS: Array<{name:string;primary:AnalysisView;views:AnalysisView[];modes?:LinkMode[]}> = [
  {name:'Trace Investigation',primary:'sequence',views:['signals','events']},
  {name:'Bus Diagnosis',primary:'load',views:['events','root-cause']},
  {name:'Golden Comparison',primary:'trace',views:['trace'],modes:['COMPARE']},
  {name:'Simulation Evaluation',primary:'simulation',views:['trace','charts']},
  {name:'ECU Deep Analysis',primary:'network',views:['messages','signals','root-cause']},
];
export function AnalysisWorkspaceTools({project,view}: {project?:string;view:AnalysisView}) {
  const connection = useAnalysisWorkspace(project);
  const [target,setTarget] = useState<AnalysisView>('signals');
  const [fallbacks,setFallbacks] = useState<Array<{view:AnalysisView;href:string}>>([]);
  const [profileName,setProfileName] = useState('Mein Analysearbeitsbereich');
  const [restore,setRestore] = useState(false);
  const [profileId,setProfileId] = useState('');
  const [notice,setNotice] = useState('');
  useEffect(() => { connection?.store.view(view); },[connection?.store,view]);
  useEffect(() => {const restoreProfile=connection?.store.profiles().find(p=>p.restore_on_start);if(restoreProfile)setProfileId(restoreProfile.profile_id);},[connection?.store]);
  if (!connection) return <div className="analysis-window-tools" aria-busy="true">Analysefenster werden vorbereitet …</div>;
  const {state,store} = connection, d = state.descriptor;
  const primary = d.primary_id === d.window_id;
  const profiles = store.profiles();
  const open = (next:AnalysisView,mode:LinkMode = 'FOLLOW_PRIMARY',size?:[number,number]) => { const href=store.open(next,mode,size); setFallbacks(current => [...current,{view:next,href}].slice(-6)); };
  const save = () => {
    const others = state.windows.filter(w => w.window_id !== d.window_id).slice(0,6);
    const p: WorkspaceProfile = {version:1,profile_id:analysisWindowId(),name:profileName.trim() || 'Analysearbeitsbereich',user_id:'local-session',project_scope:d.project_id,primary_view:view,secondary_views:others.map(w => w.view_id),link_modes:others.map(w => w.link_mode),preferred_window_sizes:others.map(w => [Math.max(320,w.width),Math.max(320,w.height)]),preferred_monitor_roles:others.map((_,i) => `Analyse ${i+1}`),restore_on_start:restore};
    try { store.saveProfile(p); setProfileId(p.profile_id); setNotice('Arbeitsbereich für dieses Projekt und diese lokale Browser-Sitzung gespeichert.'); } catch { setNotice('Der Browser erlaubt das Speichern des Arbeitsbereichs nicht.'); }
  };
  const load = () => {
    const p = profiles.find(p => p.profile_id === profileId); if (!p) return;
    setFallbacks([]); p.secondary_views.forEach((v,i) => open(v,p.link_modes[i],p.preferred_window_sizes[i]));
    setNotice(`Arbeitsbereich „${p.name}“ geöffnet. Fenster auf die gewünschten Monitore ziehen; gesperrte Fenster über die Links öffnen. Es werden keine Bearbeitungen wiederhergestellt.`);
    if(p.primary_view!==view)window.location.assign(analysisViewHref({...d,view_id:p.primary_view,context:state.context}));
  };
  return <section className="panel analysis-window-tools" aria-label="Analysefenster und Arbeitsbereich">
    <header><strong>{primary ? 'Primäransicht' : 'Analysefenster'} · {ANALYSIS_VIEWS[view]}</strong><output aria-label="Gemeinsamer Zeitcursor">Zeitcursor: {state.context.time_cursor === null ? 'Unbekannt' : `${state.context.time_cursor} s`} · {state.context.time_basis ?? 'Zeitbasis unbekannt'}</output><span className="analysis-link-status" role="status">{state.ended ? 'Sitzung beendet' : primary ? `${state.windows.length} Fenster` : d.link_mode === 'FOLLOW_PRIMARY' ? state.primary_alive ? 'Mit Primäransicht gekoppelt' : 'Primäransicht nicht erreichbar · Kontext bleibt sichtbar' : d.link_mode === 'COMPARE' ? 'Vergleich · getrennte Kontexte' : 'Unabhängiger Kontext'}</span></header>
    <div className="analysis-window-actions">
      <label><span className="analysis-control-label">Ansicht</span><select aria-label="Ansicht" value={target} onChange={e => setTarget(e.target.value as AnalysisView)}>{Object.entries(ANALYSIS_VIEWS).map(([id,label]) => <option value={id} key={id}>{label}</option>)}</select></label>
      <button className="button secondary" type="button" disabled={state.ended} onClick={() => open(target)}>↗ In neuem Fenster öffnen</button>
      <button className="button secondary" type="button" disabled={state.ended} onClick={() => open(target,'INDEPENDENT')}>Unabhängig öffnen</button>
      <button className="button secondary" type="button" disabled={state.ended} onClick={() => open('trace','COMPARE')}>⇄ Vergleich öffnen</button>
      {!primary && <label><span className="analysis-control-label">Kopplung</span><select aria-label="Fensterkopplung" value={d.link_mode} onChange={e => store.mode(e.target.value as LinkMode)}><option value="FOLLOW_PRIMARY">Primäransicht folgen</option><option value="INDEPENDENT">Unabhängig</option><option value="COMPARE">Vergleich</option></select></label>}
      <button className="button secondary tiny" type="button" onClick={() => open('assistant')}>Analyse-Assistent öffnen</button>
    </div>
    {state.error && <p className="notice" role="alert">{state.error}</p>}
    {fallbacks.length > 0 && <div className="analysis-window-links" aria-label="Analysefenster Ersatzlinks">{fallbacks.map(item => <a key={item.href} href={item.href} target="_blank" rel="noopener noreferrer">{ANALYSIS_VIEWS[item.view]} separat öffnen</a>)}</div>}
    <details><summary>Arbeitsbereiche und Fenster ({state.windows.length})</summary>
      <small>Analyseprojektion · derselbe NIS-Datenbestand. Zeitkopplung übernimmt die dokumentierte Zeitbasis; keine automatische Uhrkorrektur. Fenster können manuell auf einen zweiten Monitor gezogen werden.</small>
      <div className="analysis-profile-presets">{PRESETS.map(p => <button className="button secondary tiny" type="button" disabled={state.ended} key={p.name} onClick={() => { setFallbacks([]); p.views.forEach((v,i) => open(v,p.modes?.[i] ?? 'FOLLOW_PRIMARY')); if(p.primary!==view)window.location.assign(analysisViewHref({...d,view_id:p.primary,context:state.context})); }}>{p.name}</button>)}</div>
      <div className="analysis-profile-editor"><label>Profilname<input maxLength={180} value={profileName} onChange={e => setProfileName(e.target.value)} /></label><label className="analysis-checkbox"><input type="checkbox" checked={restore} onChange={e => setRestore(e.target.checked)} />Beim nächsten Öffnen zur Wiederherstellung anbieten</label><button className="button secondary" type="button" onClick={save}>Arbeitsbereich speichern</button><label>Gespeichertes Profil<select value={profileId} onChange={e => setProfileId(e.target.value)}><option value="">Profil auswählen</option>{profiles.map(p => <option value={p.profile_id} key={p.profile_id}>{p.name}</option>)}</select></label><button className="button secondary" type="button" disabled={!profileId} onClick={load}>Arbeitsbereich wiederherstellen</button></div>
      {profiles.some(p => p.restore_on_start) && <p role="status">Ein gespeicherter Arbeitsbereich ist zur Wiederherstellung vorgemerkt. Wähle ihn oben und öffne seine Fenster mit „Arbeitsbereich wiederherstellen“.</p>}
      <ul>{state.windows.map(w => <li key={w.window_id}>{ANALYSIS_VIEWS[w.view_id]} · {w.window_id === d.primary_id ? 'Primäransicht' : w.link_mode === 'FOLLOW_PRIMARY' ? 'Gekoppelt' : w.link_mode === 'COMPARE' ? 'Vergleich' : 'Unabhängig'} · {w.width} × {w.height}</li>)}</ul>
      <button className="button secondary tiny" type="button" onClick={() => store.end()}>Analysesitzung in allen Fenstern beenden</button>
    </details>
    {notice && <p role="status">{notice}</p>}
  </section>;
}

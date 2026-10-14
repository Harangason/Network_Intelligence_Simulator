'use client';
import { useEffect, useState } from 'react';
import { readActiveProjectId } from '@/features/settings/lib/user-settings';
import { analysisWorkspaceStore, type WorkspaceState, type WorkspaceStore } from '../lib/analysis-workspace-browser';
import { ANALYSIS_VIEWS, SIMULATION_WINDOW_VIEWS, analysisWindowId, type AnalysisView, type LinkMode, type WorkspaceProfile, type WindowDescriptor } from '../lib/analysis-workspace';
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
export function AnalysisWorkspaceTools({project,view,collapsible=false}: {project?:string;view:AnalysisView;collapsible?:boolean}) {
  const connection = useAnalysisWorkspace(project);
  const [board,setBoard] = useState<WindowDescriptor['board_id']>(collapsible ? 'simulation' : 'trace');
  const [openingMode,setOpeningMode] = useState<LinkMode>('FOLLOW_PRIMARY');
  const [target,setTarget] = useState<AnalysisView>('signals');
  const [traceTarget,setTraceTarget] = useState<AnalysisView>('trace');
  const [fallbacks,setFallbacks] = useState<Array<{view:AnalysisView;href:string;board:WindowDescriptor['board_id'];mode:LinkMode}>>([]);
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
  const simulationAvailable = d.board_id === 'simulation' || Boolean(state.context.simulation_run_id);
  const traceAvailable = Boolean(state.context.trace_id || state.context.simulation_run_id);
  const open = (next:AnalysisView,mode:LinkMode = 'FOLLOW_PRIMARY',size?:[number,number],board:WindowDescriptor['board_id']='trace') => { const href=store.open(next,mode,size,board); if(store.state.error)setFallbacks(current => [...current,{view:next,href,board,mode}].slice(-6)); };
  const links = (board:WindowDescriptor['board_id']) => fallbacks.some(f=>f.board===board) && <div className="analysis-window-links" aria-label={`${board==='simulation'?'Simulation':'Trace-Analyse'} Ersatzlinks`}>{fallbacks.filter(f=>f.board===board).map(item=><a key={item.href} href={item.href} target="_blank" rel="noopener noreferrer">{ANALYSIS_VIEWS[item.view]} · {item.mode==='FOLLOW_PRIMARY'?'Gekoppelt':item.mode==='COMPARE'?'Vergleich':'Unabhängig'} im Browser öffnen</a>)}</div>;
  const save = () => {
    const others = state.windows.filter(w => w.window_id !== d.window_id).slice(0,6);
    const p: WorkspaceProfile = {version:1,profile_id:analysisWindowId(),name:profileName.trim() || 'Analysearbeitsbereich',user_id:'local-session',project_scope:d.project_id,primary_view:view,primary_board:d.board_id,secondary_views:others.map(w => w.view_id),secondary_boards:others.map(w=>w.board_id),link_modes:others.map(w => w.link_mode),preferred_window_sizes:others.map(w => [Math.max(320,w.width),Math.max(320,w.height)]),preferred_monitor_roles:others.map((_,i) => `Analyse ${i+1}`),restore_on_start:restore};
    try { store.saveProfile(p); setProfileId(p.profile_id); setNotice('Arbeitsbereich für dieses Projekt und diese lokale Browser-Sitzung gespeichert.'); } catch { setNotice('Der Browser erlaubt das Speichern des Arbeitsbereichs nicht.'); }
  };
  const load = () => {
    const p = profiles.find(p => p.profile_id === profileId); if (!p) return;
    setFallbacks([]); p.secondary_views.forEach((v,i) => open(v,p.link_modes[i],p.preferred_window_sizes[i],p.secondary_boards?.[i] ?? (v==='simulation'?'simulation':'trace')));
    setNotice(`Arbeitsbereich „${p.name}“ geöffnet. Fenster auf die gewünschten Monitore ziehen; gesperrte Fenster über die Links öffnen. Es werden keine Bearbeitungen wiederhergestellt.`);
    const board=p.primary_board ?? (p.primary_view==='simulation'?'simulation':'trace');
    if(p.primary_view!==view || board!==d.board_id)open(p.primary_view,'INDEPENDENT',undefined,board);
  };
  const Container = collapsible ? 'details' : 'section';
  return <Container className={`panel analysis-window-tools${collapsible?' simulation-control-panel':''}`} aria-label="Analysefenster und Arbeitsbereich">
    {collapsible && <summary><span className="eyebrow">Analysefenster</span><strong>Fenster öffnen und Arbeitsbereich verwalten</strong></summary>}
    <div className="analysis-window-launcher">
      <label>Bereich<select aria-label="Fensterbereich" value={board} onChange={e => { setBoard(e.target.value as WindowDescriptor['board_id']); if (openingMode === 'COMPARE') setOpeningMode('FOLLOW_PRIMARY'); }}><option value="simulation">Simulation</option><option value="trace">Trace-Analyse</option></select></label>
      <label>Ansicht<select aria-label={board === 'simulation' ? 'Simulationsansicht' : 'Trace-Ansicht'} value={board === 'simulation' ? target : traceTarget} onChange={e => board === 'simulation' ? setTarget(e.target.value as AnalysisView) : setTraceTarget(e.target.value as AnalysisView)}>
        {(board === 'simulation' ? SIMULATION_WINDOW_VIEWS : (Object.keys(ANALYSIS_VIEWS) as AnalysisView[]).filter(v => v !== 'simulation')).map(v => <option value={v} key={v}>{ANALYSIS_VIEWS[v]}</option>)}
      </select></label>
      <label>Kopplung<select aria-label="Kopplung des neuen Fensters" value={openingMode} onChange={e => setOpeningMode(e.target.value as LinkMode)}><option value="FOLLOW_PRIMARY">Primäransicht folgen</option><option value="INDEPENDENT">Unabhängig</option>{board === 'trace' && <option value="COMPARE">Vergleich</option>}</select></label>
      <button className="button" type="button" disabled={state.ended || !(board === 'simulation' ? simulationAvailable : traceAvailable)} onClick={() => open(board === 'simulation' ? target : traceTarget, openingMode, undefined, board)}>Fenster öffnen</button>
    </div>
    <div className="analysis-window-meta"><span className="analysis-link-status" role="status">{state.ended ? 'Sitzung beendet' : primary ? `Primäransicht · ${state.windows.length} Fenster` : d.link_mode === 'FOLLOW_PRIMARY' ? state.primary_alive ? 'Mit Primäransicht gekoppelt' : 'Primäransicht nicht erreichbar · Kontext bleibt sichtbar' : d.link_mode === 'COMPARE' ? 'Vergleich · getrennte Kontexte' : 'Unabhängiger Kontext'}</span><small>Öffnet ein zusätzliches Fenster; diese Seite bleibt geöffnet.</small></div>
    {links(board)}
    {!(board === 'simulation' ? simulationAvailable : traceAvailable) && <small>{board === 'simulation' ? 'Kein zugehöriger Simulationslauf im aktuellen Kontext.' : 'Noch keine gespeicherte Trace im aktuellen Kontext.'}</small>}
    {!primary && <label className="analysis-current-coupling">Dieses Fenster<select aria-label="Fensterkopplung" value={d.link_mode} onChange={e => store.mode(e.target.value as LinkMode)}><option value="FOLLOW_PRIMARY">Primäransicht folgen</option><option value="INDEPENDENT">Unabhängig</option><option value="COMPARE">Vergleich</option></select></label>}
    {state.error && <p className="notice" role="alert">{state.error}</p>}
    <details className="analysis-workspace-settings"><summary>Arbeitsbereich verwalten</summary>
      <div className="analysis-profile-block"><strong>Fenstervorlagen</strong><div className="analysis-profile-presets">{PRESETS.map(p => <button className="button secondary tiny" type="button" disabled={state.ended || !traceAvailable || p.primary==='simulation' && !simulationAvailable} key={p.name} onClick={() => { setFallbacks([]); p.views.forEach((v,i) => open(v,p.modes?.[i] ?? 'FOLLOW_PRIMARY')); const board=p.primary==='simulation'?'simulation':'trace'; if(p.primary!==view || board!==d.board_id)open(p.primary,'FOLLOW_PRIMARY',undefined,board); }}>{p.name}</button>)}</div></div>
      <div className="analysis-profile-editor">
        <div className="analysis-profile-save"><label>Profilname<input maxLength={180} value={profileName} onChange={e => setProfileName(e.target.value)} /></label><button className="button secondary" type="button" onClick={save}>Arbeitsbereich speichern</button><label className="analysis-checkbox"><input type="checkbox" checked={restore} onChange={e => setRestore(e.target.checked)} />Beim nächsten Öffnen zur Wiederherstellung anbieten</label></div>
        <div className="analysis-profile-restore"><label>Gespeichertes Profil<select value={profileId} onChange={e => setProfileId(e.target.value)}><option value="">Profil auswählen</option>{profiles.map(p => <option value={p.profile_id} key={p.profile_id}>{p.name}</option>)}</select></label><button className="button secondary" type="button" disabled={!profileId} onClick={load}>Arbeitsbereich wiederherstellen</button></div>
      </div>
      {profiles.some(p => p.restore_on_start) && <p role="status">Ein gespeicherter Arbeitsbereich ist zur Wiederherstellung vorgemerkt. Wähle ihn oben und öffne seine Fenster mit „Arbeitsbereich wiederherstellen“.</p>}
      <div className="analysis-workspace-footer"><div><strong>Offene Fenster</strong><ul>{state.windows.map(w => <li key={w.window_id}>{w.board_id==='simulation'?'Simulation':'Trace-Analyse'} · {ANALYSIS_VIEWS[w.view_id]} · {w.window_id === d.primary_id ? 'Primäransicht' : w.link_mode === 'FOLLOW_PRIMARY' ? 'Gekoppelt' : w.link_mode === 'COMPARE' ? 'Vergleich' : 'Unabhängig'} · {w.width} × {w.height}</li>)}</ul></div><button className="button secondary tiny" type="button" onClick={() => store.end()}>Analysesitzung in allen Fenstern beenden</button></div>
      <small>Zeitcursor: {state.context.time_cursor === null ? 'Unbekannt' : `${state.context.time_cursor} s`} · {state.context.time_basis ?? 'Zeitbasis unbekannt'}. Die Kopplung folgt dieser Zeitbasis. Fenster können auf einen zweiten Monitor gezogen werden.</small>
    </details>
    {notice && <p role="status">{notice}</p>}
  </Container>;
}

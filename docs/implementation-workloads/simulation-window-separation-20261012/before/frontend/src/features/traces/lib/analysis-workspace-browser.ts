import { analysisViewHref, analysisWindowId, contextFromSearch, contextWithPatch, validatedContext, validatedDescriptor, validProfile, type AnalysisContext, type AnalysisView, type LinkMode, type WindowDescriptor, type WorkspaceProfile } from './analysis-workspace.ts';
export type WorkspaceState = { descriptor: WindowDescriptor; context: AnalysisContext; revision: number; received: number; windows: WindowDescriptor[]; primary_alive: boolean; ended: boolean; error: string };
type Packet = { protocol:1; workspace:string; project:string; from:string; primary:string; type:'HELLO'|'STATE'|'PATCH'|'REGISTER'|'CLOSED'|'LOGOUT'; revision:number; context?:AnalysisContext; patch?:Partial<AnalysisContext>; source?:string|null; descriptor?:WindowDescriptor };
let store: WorkspaceStore | null = null;
export function readAnalysisWorkspace() { return store?.state ?? null; }
export function analysisWorkspaceStore(project: string): WorkspaceStore {
  if (store?.state.descriptor.project_id !== project) { if(store && store.state.descriptor.window_id===store.state.descriptor.primary_id)store.end(); store?.dispose(); store = new WorkspaceStore(project); }
  return store;
}
const safeId = (v: string | null) => v && /^[a-zA-Z0-9_-]{1,100}$/.test(v) ? v : analysisWindowId();
export class WorkspaceStore {
  state: WorkspaceState;
  private listeners = new Set<() => void>();
  private channel: BroadcastChannel | null = null;
  private timer: number;
  private key: string;
  private lastPrimary = 0;
  private clock = Date.now();
  private receivedRevision = -1;
  private unload: () => void;
  private storage: (event: StorageEvent) => void;
  constructor(project: string) {
    const p = new URLSearchParams(window.location.search), id = safeId(p.get('window'));
    const descriptor: WindowDescriptor = { window_id:id, workspace_id:safeId(p.get('workspace')), primary_id:p.get('primary') ? safeId(p.get('primary')) : id, project_id:project, board_id:window.location.pathname.includes('simulation') ? 'simulation':'trace', view_id:contextFromSearch(project,window.location.search).view_mode, link_mode:['FOLLOW_PRIMARY','INDEPENDENT','COMPARE'].includes(p.get('link') ?? '') ? p.get('link') as LinkMode : 'FOLLOW_PRIMARY', context:contextFromSearch(project,window.location.search), width:window.outerWidth, height:window.outerHeight, last_position:[window.screenX,window.screenY], created_at:Date.now(), last_active_at:Date.now() };
    this.state = { descriptor, context:descriptor.context, revision:0, received:0, windows:[descriptor], primary_alive:descriptor.primary_id === id, ended:false, error:'' };
    // Keep identity stable through reload and existing Next.js view navigation.
    for (const [key,value] of Object.entries({workspace:descriptor.workspace_id,window:id,primary:descriptor.primary_id,link:descriptor.link_mode})) p.set(key,value);
    window.history.replaceState(window.history.state,'',`${window.location.pathname}?${p}${window.location.hash}`);
    this.key = `nis.analysis.v1.${encodeURIComponent(project)}.${descriptor.workspace_id}`;
    try { this.channel = new BroadcastChannel(this.key); this.channel.onmessage = event => this.receive(event.data); } catch { /* Older browsers use storage events for metadata only. */ }
    this.storage = event => { if (event.key === this.key && event.newValue) try { this.receive(JSON.parse(event.newValue)); } catch { /* Invalid packets never change context. */ } };
    window.addEventListener('storage',this.storage);
    this.unload = () => this.send('CLOSED');
    window.addEventListener('pagehide',this.unload);
    this.timer = window.setInterval(() => this.register(),5000);
    this.register(); this.send('HELLO');
  }
  subscribe = (fn: () => void) => { this.listeners.add(fn); return () => { this.listeners.delete(fn); }; };
  snapshot = () => this.state;
  private emit() { this.listeners.forEach(fn => fn()); window.dispatchEvent(new Event('engineering:assistant-context')); }
  private send(type: Packet['type'], context?: AnalysisContext, patch?:Partial<AnalysisContext>) {
    const d = this.state.descriptor;
    const packet: Packet = { protocol:1, workspace:d.workspace_id, project:d.project_id, from:d.window_id, primary:d.primary_id, type, revision:this.clock, ...(context ? {context}:{}), ...(patch?{patch,source:this.state.context.trace_id??this.state.context.simulation_run_id}:{}), ...(['REGISTER','HELLO'].includes(type) ? {descriptor:d}:{}) };
    if (this.channel) this.channel.postMessage(packet);
    else try { window.localStorage.setItem(this.key,JSON.stringify(packet)); window.localStorage.removeItem(this.key); } catch { this.state = {...this.state,error:'Fensterkopplung ist im Browser gesperrt. Unabhängige Analyse bleibt verfügbar.'}; this.emit(); }
  }
  private receive(value: unknown) {
    if (!value || typeof value !== 'object' || JSON.stringify(value).length > 32000) return;
    const p = value as Packet, d = this.state.descriptor;
    if (p.protocol !== 1 || p.project !== d.project_id || p.workspace !== d.workspace_id || p.primary !== d.primary_id || p.from === d.window_id || typeof p.from !== 'string' || !Number.isSafeInteger(p.revision)) return;
    if (p.type === 'LOGOUT') { this.end(false); return; }
    if (this.state.ended) return;
    if (p.type === 'CLOSED') { this.state = {...this.state,windows:this.state.windows.filter(w => w.window_id !== p.from), primary_alive:p.from === d.primary_id ? false:this.state.primary_alive}; this.emit(); return; }
    if ((p.type === 'REGISTER' || p.type === 'HELLO') && p.descriptor) {
      const peer = validatedDescriptor(p.descriptor,d.project_id), context=peer?.context;
      if (!peer || !context || peer.window_id !== p.from || peer.workspace_id !== d.workspace_id || peer.primary_id !== d.primary_id || Math.abs(Date.now()-peer.last_active_at)>30000) return;
      const windows = [...this.state.windows.filter(w => w.window_id !== p.from && Date.now()-w.last_active_at<20000),{...peer,context}].slice(-12);
      if (p.from === d.primary_id) this.lastPrimary = Date.now();
      this.state = {...this.state,windows,primary_alive:d.window_id === d.primary_id || Date.now()-this.lastPrimary<20000}; this.emit();
      if (d.window_id === d.primary_id && p.type === 'HELLO') this.send('STATE',this.state.context);
      return;
    }
    if (p.type === 'PATCH' && d.window_id === d.primary_id) {
      if (!p.patch || p.source !== (this.state.context.trace_id??this.state.context.simulation_run_id)) { this.send('STATE',this.state.context); return; }
      const next=contextWithPatch(this.state.context,p.patch); if (!next) return;
      this.update(p.patch); this.state={...this.state,received:this.state.received+1}; this.emit(); return;
    }
    const context = validatedContext(p.context,d.project_id); if (!context) return;
    if (p.type !== 'STATE' || p.from !== d.primary_id || d.link_mode !== 'FOLLOW_PRIMARY' || p.revision <= this.receivedRevision) return;
    this.receivedRevision = p.revision; this.lastPrimary = Date.now();
    this.state = {...this.state,context,revision:this.state.revision+1,received:this.state.received+1,primary_alive:true}; this.emit();
  }
  update(patch: Partial<AnalysisContext>) {
    if (this.state.ended) return;
    const context = contextWithPatch(this.state.context,patch); if (!context || JSON.stringify(context) === JSON.stringify(this.state.context)) return;
    const d = this.state.descriptor;
    if (d.link_mode === 'FOLLOW_PRIMARY' && d.window_id !== d.primary_id) {
      // Followers request a context change; only the primary orders and broadcasts it.
      const changed = Object.fromEntries(Object.entries(context).filter(([key,value])=>JSON.stringify(value)!==JSON.stringify(this.state.context[key as keyof AnalysisContext]))) as Partial<AnalysisContext>;
      this.send('PATCH',undefined,changed);
      return;
    }
    this.clock = Math.max(this.clock+1,Date.now());
    this.state = {...this.state,context,revision:this.state.revision+1,descriptor:{...d,context}}; this.emit();
    if (d.window_id === d.primary_id) this.send('STATE',context);
  }
  mode(mode: LinkMode) {
    if (this.state.descriptor.window_id === this.state.descriptor.primary_id && mode === 'FOLLOW_PRIMARY') return;
    this.receivedRevision = -1;
    this.state = {...this.state,descriptor:{...this.state.descriptor,link_mode:mode}}; this.emit(); this.register();
    const params=new URLSearchParams(window.location.search);params.set('link',mode);window.history.replaceState(window.history.state,'',`${window.location.pathname}?${params}${window.location.hash}`);
    if (mode === 'FOLLOW_PRIMARY') this.send('HELLO');
  }
  view(view: AnalysisView) { this.state = {...this.state,descriptor:{...this.state.descriptor,view_id:view}}; this.register(); }
  private register() {
    if (this.state.ended) return;
    const descriptor = {...this.state.descriptor,context:this.state.context,width:window.outerWidth,height:window.outerHeight,last_position:[window.screenX,window.screenY] as [number,number],last_active_at:Date.now()};
    this.state = {...this.state,descriptor,windows:[...this.state.windows.filter(w => w.window_id !== descriptor.window_id && Date.now()-w.last_active_at<20000),descriptor],primary_alive:descriptor.window_id === descriptor.primary_id || Date.now()-this.lastPrimary<20000};
    this.send('REGISTER'); this.emit();
  }
  open(view: AnalysisView, mode: LinkMode = 'FOLLOW_PRIMARY', size: [number,number] = [1200,900]): string {
    const d = this.state.descriptor;
    const child = {...d,window_id:analysisWindowId(),board_id:view === 'simulation' ? 'simulation' as const:'trace' as const,view_id:view,link_mode:mode,context:this.state.context};
    const href = analysisViewHref(child);
    const popup = window.open(href,`nis-${child.window_id}`,`popup=yes,width=${size[0]},height=${size[1]}`);
    if (popup) popup.opener = null;
    this.state = {...this.state,error:popup ? '':'Der Browser hat das Fenster blockiert. Öffne die Ansicht über den Ersatzlink.'}; this.emit();
    return href;
  }
  profiles(): WorkspaceProfile[] { try { const all: unknown = JSON.parse(localStorage.getItem(`nis.analysis.profiles.v1.${this.state.descriptor.project_id}`) ?? '[]'); return Array.isArray(all) ? all.filter(p => validProfile(p,this.state.descriptor.project_id)).slice(0,20) : []; } catch { return []; } }
  saveProfile(profile: WorkspaceProfile) { if (!validProfile(profile,this.state.descriptor.project_id)) return; localStorage.setItem(`nis.analysis.profiles.v1.${profile.project_scope}`,JSON.stringify([...this.profiles().filter(p => p.profile_id !== profile.profile_id),profile].slice(-20))); this.emit(); }
  end(broadcast = true) {
    if (broadcast) this.send('LOGOUT');
    const context=contextFromSearch(this.state.descriptor.project_id,'');
    this.state = {...this.state,context,descriptor:{...this.state.descriptor,context},windows:[],ended:true};
    this.emit(); window.dispatchEvent(new Event('nis:analysis-session-ended'));
  }
  dispose() { window.clearInterval(this.timer); this.send('CLOSED'); this.channel?.close(); window.removeEventListener('storage',this.storage); window.removeEventListener('pagehide',this.unload); this.listeners.clear(); }
}

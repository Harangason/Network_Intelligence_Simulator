"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { EngFunction } from '@/lib/types';
import { busProfiles, type NetworkTopology } from '@/lib/topology';
import { buildHardwareGraph, visibleHardwareGraph, nodePath, fitGraph2D, graphLinkPath, kindColors, kindLabels, compareNames, type DiagramMode, type GraphKind, type ViewTransform } from '@/lib/hardware-graph';
import type { ThreeGraphHandle, ThreeGraphData } from '@/lib/hardware-graph-three';

export function HardwareTopologyView({ functions, topology }: { functions: EngFunction[]; topology: NetworkTopology }) {
  const [mode, setMode] = useState<DiagramMode>('hardware');
  const [dimension, setDimension] = useState<'2d' | '3d'>('2d');
  const [query, setQuery] = useState(''), [kind, setKind] = useState(''), [bus, setBus] = useState('');
  const [labels, setLabels] = useState(true), [physical, setPhysical] = useState(true);
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set());
  const [depth, setDepth] = useState(Infinity), [playing, setPlaying] = useState(false);
  const [selected, setSelected] = useState(''), [selectedLink, setSelectedLink] = useState('');
  const [rotation, setRotation] = useState(false), [follow, setFollow] = useState(false);
  const [threeStatus, setThreeStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [size, setSize] = useState({ width: 900, height: 720 });
  const [transform, setTransform] = useState<ViewTransform>({ x: 450, y: 360, scale: .35 });
  const [panning, setPanning] = useState(false);
  const viewRef = useRef<HTMLElement>(null), stageRef = useRef<HTMLDivElement>(null), threeRef = useRef<HTMLDivElement>(null);
  const threeHandle = useRef<ThreeGraphHandle | null>(null);
  const drag = useRef<{ id: number; x: number; y: number; transform: ViewTransform; moved: boolean } | null>(null);
  const suppressClick = useRef(false);
  const graph = useMemo(() => buildHardwareGraph(topology, functions, mode), [topology, functions, mode]);
  const visible = useMemo(() => visibleHardwareGraph(graph, { query, kind, bus, depth, collapsed, physical }), [graph, query, kind, bus, depth, collapsed, physical]);
  const selectedNode = graph.byId.get(selected), link = graph.links.find(l => l.id === selectedLink);
  const focusIds = useMemo(() => {
    const ids = new Set(nodePath(graph, selected).map(n => n.id));
    if (selected) for (const edge of graph.links) if (edge.source === selected || edge.target === selected) { ids.add(edge.source); ids.add(edge.target); }
    if (link) { ids.add(link.source); ids.add(link.target); }
    return ids;
  }, [graph, selected, link]);
  const select = useCallback((id: string) => { setSelected(id); setSelectedLink(''); setPlaying(false); }, []);
  const expand = useCallback((id: string) => { setPlaying(false); setCollapsed(current => { const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); return next; }); }, []);
  const selectLink = useCallback((id: string) => { setSelectedLink(id); setSelected(''); setPlaying(false); }, []);
  const threeData = useMemo<ThreeGraphData>(() => ({ nodes: visible.nodes, links: visible.links, selected, labels, focusIds }), [visible, selected, labels, focusIds]);
  const dataRef = useRef(threeData); dataRef.current = threeData;
  const visibleLabels = useMemo(() => {
    if (!labels) return new Set<string>();
    const priority = (id: string, type: GraphKind) => id === selected ? -5 : focusIds.has(id) ? -4 : type === 'root' ? -3 : type === 'group' ? -2 : type === 'ecu' || type === 'gateway' ? -1 : 0;
    const rectangles: { x: number; y: number; width: number; height: number }[] = [];
    const result = new Set<string>();
    for (const node of [...visible.nodes].sort((a, b) => priority(a.id, a.kind) - priority(b.id, b.kind) || compareNames(a, b))) {
      const x = transform.x + (node.x + 13) * transform.scale, y = transform.y + node.y * transform.scale - 9;
      const fontSize = Math.max(10, 12 * transform.scale), width = Math.min(25, node.name.length) * fontSize * .6 + 5, height = fontSize + 5;
      if (x < 0 || x + width > size.width || y < 0 || y + height > size.height) continue;
      if (rectangles.some(r => x < r.x + r.width && x + width > r.x && y < r.y + r.height && y + height > r.y)) continue;
      result.add(node.id); rectangles.push({ x, y, width, height });
    }
    return result;
  }, [labels, visible.nodes, selected, focusIds, transform, size]);

  useEffect(() => {
    if (!stageRef.current) return;
    const observer = new ResizeObserver(([entry]) => setSize({ width: Math.max(1, entry.contentRect.width), height: Math.max(1, entry.contentRect.height) }));
    observer.observe(stageRef.current); return () => observer.disconnect();
  }, []);
  useEffect(() => { setTransform(fitGraph2D(visible.nodes, size.width, size.height)); }, [visible.nodes, size]);
  useEffect(() => {
    const stage = stageRef.current;
    if (!stage || dimension !== '2d') return;
    const wheel = (event: WheelEvent) => {
      event.preventDefault();
      const rect = stage.getBoundingClientRect(), x = event.clientX - rect.left, y = event.clientY - rect.top;
      setTransform(t => { const scale = Math.max(.05, Math.min(6, t.scale * Math.exp(-event.deltaY * .001))); return { x: x - (x - t.x) * scale / t.scale, y: y - (y - t.y) * scale / t.scale, scale }; });
    };
    stage.addEventListener('wheel', wheel, { passive: false });
    return () => stage.removeEventListener('wheel', wheel);
  }, [dimension]);
  useEffect(() => {
    if (!playing) return;
    if (depth >= graph.maxDepth) { setPlaying(false); return; }
    const timer = setTimeout(() => setDepth(d => Math.min(graph.maxDepth, d + 1)), 950);
    return () => clearTimeout(timer);
  }, [playing, depth, graph.maxDepth]);
  useEffect(() => {
    if (dimension !== '3d' || !threeRef.current) return;
    let disposed = false;
    setThreeStatus('loading');
    void import('@/lib/hardware-graph-three').then(({ createThreeGraph }) => {
      if (disposed || !threeRef.current) return;
      const handle = createThreeGraph(threeRef.current, { select, expand, link: selectLink, rotation: setRotation, error: () => setThreeStatus('error') });
      threeHandle.current = handle; handle.update(dataRef.current); setThreeStatus('ready');
    }).catch(() => { if (!disposed) setThreeStatus('error'); });
    return () => { disposed = true; threeHandle.current?.dispose(); threeHandle.current = null; setRotation(false); };
  }, [dimension, select, expand, selectLink]);
  useEffect(() => { threeHandle.current?.update(threeData); }, [threeData]);
  useEffect(() => { threeHandle.current?.fit(); }, [visible.nodes]);
  useEffect(() => { if (follow && selected) threeHandle.current?.focus(selected); }, [selected, follow, threeStatus]);
  useEffect(() => { if (selected && !graph.byId.has(selected)) setSelected(''); if (selectedLink && !graph.links.some(l => l.id === selectedLink)) setSelectedLink(''); }, [graph, selected, selectedLink]);

  const fit = () => { if (dimension === '3d') threeHandle.current?.fit(); else setTransform(fitGraph2D(visible.nodes, size.width, size.height)); };
  const zoomAt = (factor: number, x = size.width / 2, y = size.height / 2) => setTransform(t => {
    const scale = Math.max(.05, Math.min(6, t.scale * factor));
    return { x: x - (x - t.x) * scale / t.scale, y: y - (y - t.y) * scale / t.scale, scale };
  });
  const zoom = (factor: number) => dimension === '3d' ? threeHandle.current?.zoom(factor) : zoomAt(factor);
  const focus = (id: string) => {
    const node = graph.byId.get(id); if (!node) return;
    if (dimension === '3d') { threeHandle.current?.focus(id); return; }
    const scale = Math.max(transform.scale, 1.1);
    setTransform({ x: size.width / 2 - node.x * scale, y: size.height / 2 - node.y * scale, scale });
  };
  const reveal = (id: string) => {
    setDepth(Infinity); setCollapsed(current => { const next = new Set(current); nodePath(graph, id).forEach(n => next.delete(n.id)); return next; });
    select(id);
  };
  const reset = (all: boolean) => { setPlaying(false); setQuery(''); setKind(''); setBus(''); setCollapsed(new Set()); setDepth(all ? Infinity : 0); setSelected(''); setSelectedLink(''); };
  const switchMode = (next: DiagramMode) => { setMode(next); reset(true); };
  const neighbors = selectedNode ? graph.links.filter(l => l.kind !== 'hierarchy' && (l.source === selected || l.target === selected)).sort((a, b) => compareNames(graph.byId.get(a.source === selected ? a.target : a.source)!, graph.byId.get(b.source === selected ? b.target : b.source)!)) : [];
  const hardware = selectedNode?.hardware;

  return <section className="hardware-topology-view hardware-explorer" aria-label="Hardware-Topologie" ref={viewRef}>
    <div className="hardware-topology-header">
      <div><span>Hardware-Topologie</span><strong>Zusammenhänge erkunden</strong></div>
      <div className="hardware-topology-toolbar" role="toolbar" aria-label="Darstellung">
        {(['hardware', 'functions', 'combined'] as const).map(value => <button key={value} type="button" aria-pressed={mode === value} className={mode === value ? 'active' : ''} onClick={() => switchMode(value)}>{{ hardware: 'Hardware', functions: 'Functions', combined: 'Combined' }[value]}</button>)}
        <span className="hardware-toolbar-divider" />
        {(['2d', '3d'] as const).map(value => <button type="button" key={value} aria-pressed={dimension === value} className={dimension === value ? 'active' : ''} onClick={() => setDimension(value)}>{value.toUpperCase()}</button>)}
        <button type="button" onClick={() => { if (document.fullscreenElement) void document.exitFullscreen(); else void viewRef.current?.requestFullscreen().catch(() => {}); }}>Vollbild</button>
      </div>
    </div>
    <div className="hardware-explorer-filters">
      <label>Suche<input type="search" aria-label="Topologie durchsuchen" placeholder="Gerät, Funktion oder Systemrahmen …" value={query} onChange={e => { setQuery(e.target.value); setPlaying(false); }} onKeyDown={e => { if (e.key === 'Enter') e.preventDefault(); }} /></label>
      <label>Typ<select aria-label="Knotentyp" value={kind} onChange={e => { setKind(e.target.value); setPlaying(false); }}><option value="">Alle Typen</option>{Object.entries(kindLabels).filter(([k]) => k !== 'root').sort((a, b) => a[1].localeCompare(b[1], 'de')).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
      <label>Bus<select aria-label="Bustyp filtern" value={bus} onChange={e => { setBus(e.target.value); setPlaying(false); }}><option value="">Alle Bustypen</option>{Object.entries(busProfiles).sort((a, b) => a[1].label.localeCompare(b[1].label, 'de')).map(([id, profile]) => <option key={id} value={id}>{profile.label}</option>)}</select></label>
      <button type="button" onClick={() => { setQuery(''); setKind(''); setBus(''); }}>Filter löschen</button>
    </div>
    <div className="hardware-topology-toolbar hardware-explorer-navigation" role="toolbar" aria-label="Graph-Navigation">
      <button type="button" aria-label="Graph verkleinern" onClick={() => zoom(1 / 1.2)}>−</button>
      {dimension === '2d' && <output aria-label="Graph Zoom">{Math.round(transform.scale * 100)} %</output>}
      <button type="button" aria-label="Graph vergrößern" onClick={() => zoom(1.2)}>+</button>
      <button type="button" onClick={fit}>Fit</button>
      <button type="button" disabled={!selected || !visible.nodes.some(n => n.id === selected)} onClick={() => focus(selected)}>Auswahl zentrieren</button>
      <button type="button" aria-pressed={labels} className={labels ? 'active' : ''} onClick={() => setLabels(l => !l)}>Labels</button>
      <button type="button" aria-pressed={physical} className={physical ? 'active' : ''} onClick={() => setPhysical(p => !p)}>Verbindungen</button>
      <button type="button" onClick={() => reset(false)}>Anfang</button>
      <button type="button" disabled={depth >= graph.maxDepth && !query && !kind && !bus} onClick={() => { setPlaying(false); setQuery(''); setKind(''); setBus(''); setDepth(d => Math.min(graph.maxDepth, (Number.isFinite(d) ? d : 0) + 1)); }}>Schritt</button>
      <button type="button" aria-pressed={playing} onClick={() => { if (playing) setPlaying(false); else { reset(false); setPlaying(true); } }}>{playing ? 'Pause' : 'Aufbau abspielen'}</button>
      <button type="button" onClick={() => reset(true)}>Alle ausklappen</button>
      {dimension === '3d' && <><button type="button" aria-pressed={rotation} className={rotation ? 'active' : ''} disabled={threeStatus !== 'ready'} onClick={() => threeHandle.current?.rotate(!rotation)}>Auto-Rotation</button><button type="button" aria-pressed={follow} className={follow ? 'active' : ''} onClick={() => setFollow(f => !f)}>Kamera folgt Auswahl</button></>}
    </div>
    <div className="hardware-explorer-workspace">
      <div className="hardware-topology-canvas">
        <div className={`hardware-topology-stage ${panning ? 'panning' : ''}`} ref={stageRef}>
          {dimension === '2d' ? <svg className="hardware-explorer-svg" width="100%" height="100%" role="group" aria-label="Radiale Hardware-Topologie" tabIndex={0}
            onPointerDown={e => { if (e.button !== 0) return; suppressClick.current = false; drag.current = { id: e.pointerId, x: e.clientX, y: e.clientY, transform, moved: false }; }}
            onPointerMove={e => { const start = drag.current; if (!start || start.id !== e.pointerId) return; const dx = e.clientX - start.x, dy = e.clientY - start.y; if (Math.hypot(dx, dy) > 5) { start.moved = true; suppressClick.current = true; e.currentTarget.setPointerCapture(e.pointerId); setPanning(true); setTransform({ ...start.transform, x: start.transform.x + dx, y: start.transform.y + dy }); } }}
            onPointerUp={e => { drag.current = null; setPanning(false); if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId); }}
            onPointerCancel={() => { if (drag.current) setTransform(drag.current.transform); drag.current = null; setPanning(false); suppressClick.current = true; }}
            onClickCapture={e => { if (suppressClick.current) { e.stopPropagation(); suppressClick.current = false; } }}
            onKeyDown={e => { if (e.target !== e.currentTarget) return; if (e.key.toLowerCase() === 'r') { e.preventDefault(); fit(); } else if (e.key === '+' || e.key === '=') { e.preventDefault(); zoom(1.2); } else if (e.key === '-') { e.preventDefault(); zoom(1 / 1.2); } else if (e.key.startsWith('Arrow')) { e.preventDefault(); setTransform(t => ({ ...t, x: t.x + (e.key === 'ArrowLeft' ? 45 : e.key === 'ArrowRight' ? -45 : 0), y: t.y + (e.key === 'ArrowUp' ? 45 : e.key === 'ArrowDown' ? -45 : 0) })); } }}>
            <g data-graph-transform="true" transform={`translate(${transform.x} ${transform.y}) scale(${transform.scale})`}>
              {visible.links.map(edge => { const source = graph.byId.get(edge.source)!, target = graph.byId.get(edge.target)!; return <path key={edge.id} data-graph-link-id={edge.id} className={`hardware-explorer-edge ${edge.kind} ${selectedLink === edge.id ? 'selected' : ''}`} d={graphLinkPath(source, target, edge.kind)} stroke={edge.bus ? busProfiles[edge.bus].color : edge.kind === 'mapping' ? '#bc9bff' : '#496373'} onClick={() => selectLink(edge.id)}><title>{source.name} — {target.name} · {edge.kind === 'physical' ? busProfiles[edge.bus!].label : edge.kind === 'mapping' ? 'Funktionszuordnung' : 'Struktur'}</title></path>; })}
              {visible.nodes.map(node => <g key={node.id} data-graph-node-id={node.id} className={`hardware-explorer-node ${selected === node.id ? 'selected' : ''} ${focusIds.size && !focusIds.has(node.id) ? 'dimmed' : ''}`} style={{ color: kindColors[node.kind] }} transform={`translate(${node.x} ${node.y})`} role="button" tabIndex={0} aria-label={`${node.name} · ${kindLabels[node.kind]}`} onClick={() => select(node.id)} onDoubleClick={() => expand(node.id)} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); select(node.id); } }}>
                <circle r={node.kind === 'root' ? 16 : node.kind === 'group' ? 10 : 7} />
                <title>{node.name} · {kindLabels[node.kind]}</title>
                {visibleLabels.has(node.id) && <text x={13} y={4} className="hardware-explorer-label" style={{ fontSize: Math.max(12, 10 / transform.scale) }}>{collapsed.has(node.id) && node.children.length ? '+ ' : ''}{node.name.length > 25 ? `${node.name.slice(0, 23)}…` : node.name}</text>}
              </g>)}
            </g>
          </svg> : <><div className="hardware-three-host" ref={threeRef} />{threeStatus === 'loading' && <div className="hardware-explorer-notice" role="status">3D-Ansicht wird geladen …</div>}{threeStatus === 'error' && <div className="hardware-explorer-notice" role="alert">3D konnte auf diesem Gerät nicht gestartet werden.<button type="button" onClick={() => setDimension('2d')}>2D öffnen</button></div>}</>}
          {!visible.nodes.length && <div className="hardware-explorer-notice" role="status">Keine passenden Knoten. Passe die Suche oder Filter an.</div>}
        </div>
        <div className="hardware-explorer-caption"><span>{visible.nodes.length} / {graph.nodes.length} Knoten · Ebene {Math.min(depth, graph.maxDepth)} / {graph.maxDepth}</span><span>{dimension === '2d' ? 'Ziehen: verschieben · Rad: zoomen · Doppelklick: Zweig auf/zu' : 'Ziehen: drehen · Umschalt/Rechts + Ziehen: verschieben · Rad: zoomen'}</span></div>
      </div>
      <aside className="hardware-explorer-details" aria-label="Topologie-Details">
        {query || kind || bus ? <div className="hardware-explorer-results"><h3>{visible.matches.length} Treffer</h3><div>{visible.matches.map(node => <button key={node.id} type="button" className={selected === node.id ? 'selected' : ''} onClick={() => reveal(node.id)}><span>{node.name}</span><small>{kindLabels[node.kind]}</small></button>)}</div></div> : null}
        {selectedNode ? <>
          <small>{selectedNode.groupRole === 'frame' ? 'Systemrahmen' : selectedNode.groupRole === 'cluster' ? 'Cluster' : kindLabels[selectedNode.kind]}</small><h3>{selectedNode.name}</h3>
          <nav className="hardware-explorer-path" aria-label="Zuordnungspfad">{nodePath(graph, selected).map(node => <button type="button" key={node.id} onClick={() => reveal(node.id)}>{node.name}</button>)}</nav>
          {!visible.nodes.some(n => n.id === selected) && <p>Die Auswahl ist durch die aktuellen Filter ausgeblendet.</p>}
          {selectedNode.children.length > 0 && <button type="button" onClick={() => expand(selected)}>{collapsed.has(selected) ? 'Zweig ausklappen' : 'Zweig einklappen'}</button>}
          {hardware && <><h4>Anschlüsse · {hardware.ports.length}</h4><ul>{[...hardware.ports].sort(compareNames).map(port => <li key={port.id}><strong>{busProfiles[port.bus].label}</strong><span>{topology.scene?.buses.find(b => b.id === port.physicalNetworkId)?.labelText || port.physicalNetworkName || port.name}</span></li>)}</ul></>}
          {selectedNode.functionRef && <><h4>Funktion</h4><p>{selectedNode.functionRef.description || 'Keine Beschreibung hinterlegt.'}</p><p>{selectedNode.kind === 'unmapped' ? 'Keine Hardware zugeordnet.' : 'Hardware-Zuordnung vorhanden.'}</p></>}
          <h4>Verbindungen und Zuordnungen · {neighbors.length}</h4><div className="hardware-explorer-neighbors">{neighbors.map(edge => { const other = graph.byId.get(edge.source === selected ? edge.target : edge.source)!; return <button key={edge.id} type="button" onClick={() => reveal(other.id)}>{other.name}<small>{edge.bus ? busProfiles[edge.bus].label : 'Funktionszuordnung'}</small></button>; })}{!neighbors.length && <p>Keine direkten Verbindungen in dieser Darstellung.</p>}</div>
          <details><summary>Technische Kennung</summary><code>{hardware?.engineeringId || selectedNode.functionRef?.id || selectedNode.id}</code></details>
        </> : link ? <><small>{link.kind === 'physical' ? 'Verbindung' : link.kind === 'mapping' ? 'Funktionszuordnung' : 'Struktur'}</small><h3>{graph.byId.get(link.source)?.name} — {graph.byId.get(link.target)?.name}</h3>{[link.source, link.target].map(id => <button type="button" key={id} onClick={() => reveal(id)}>{graph.byId.get(id)?.name}</button>)}{link.bus && <p>{busProfiles[link.bus].label}</p>}{link.edge?.description && <p>{link.edge.description}</p>}</> : <><small>Auswahl</small><h3>Topologie entdecken</h3><p>Wähle ein Gerät, eine Funktion oder eine Verbindung. Suche und Filter behalten den zugehörigen Strukturpfad im Bild.</p><p>Mit „Aufbau abspielen“ wird die Hierarchie Ebene für Ebene sichtbar.</p></>}
        <div className="hardware-explorer-key"><h4>Knotentypen</h4>{Object.entries(kindLabels).filter(([id]) => graph.nodes.some(n => n.kind === id)).map(([id, label]) => <button type="button" key={id} aria-pressed={kind === id} onClick={() => { setKind(k => k === id ? '' : id); setPlaying(false); }}><i style={{ background: kindColors[id as GraphKind] }} />{label}</button>)}</div>
      </aside>
    </div>
    <p className="hardware-explorer-footnote">Schematische Strukturansicht aus dem Projektmodell. 3D-Abstände zeigen die Hierarchie, keine vermessenen Einbauorte. Linien ohne Pfeile: Struktur grau, Busverbindungen farbig, Funktionszuordnung violett.</p>
  </section>;
}

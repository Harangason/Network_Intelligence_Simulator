"use client";

import { useEffect, useState } from 'react';
import { getNetworkView, type NetworkView } from '@/lib/workflow-api';
import { readActiveProjectId } from '@/lib/user-settings';
import { busProfiles } from '@/lib/topology';
import styles from './routing-system-frame.module.css';

export function useRoutingSystemFrameView() {
  const [state, setState] = useState<{ view: NetworkView | null; error: string }>({ view: null, error: '' });
  useEffect(() => {
    let active = true;
    const project = readActiveProjectId();
    void getNetworkView().then(view => {
      if (active && readActiveProjectId() === project && view.project_id === project) setState({ view, error: '' });
    }).catch(() => {
      if (active) setState({ view: null, error: 'Der Systemrahmen konnte nicht geladen werden.' });
    });
    return () => { active = false; };
  }, []);
  return state;
}

const kinds = { ecu: 'ECU', gateway: 'Gateway', sensor: 'Sensor', actuator: 'Aktor' };

export function RoutingSystemFrame({ nodeId, state }: { nodeId: string; state: ReturnType<typeof useRoutingSystemFrameView> }) {
  const { view, error } = state;
  if (!view) return <div className={styles.panel} role="status">{error || 'Systemrahmen laden …'}</div>;
  const topology = view.topology;
  const selected = topology.nodes.filter(node => node.id === nodeId || node.engineeringId === nodeId);
  const ids = new Set(selected.map(node => node.id));
  const frames = topology.scene?.frames.filter(frame => ids.has(frame.id) || frame.memberIds.some(id => ids.has(id))) ?? [];
  if (!frames.length) return <div className={styles.panel}><span className={styles.eyebrow}>Systemrahmen</span><p>Kein Systemrahmen in der gespeicherten Netzwerkansicht zugeordnet.</p></div>;
  return <div className={styles.panel} aria-label="Systemrahmen des Empfängers">
    {frames.map(frame => {
      const members = new Set([frame.id, ...frame.memberIds]);
      const nodes = topology.nodes.filter(node => members.has(node.id));
      const buses = topology.scene?.buses.filter(bus => bus.branches.some(branch => members.has(branch.nodeId))) ?? [];
      const cluster = topology.scene?.clusters.find(item => item.id === frame.clusterId);
      return <figure className={styles.frame} key={frame.id}>
        <figcaption><span className={styles.eyebrow}>Systemrahmen</span><strong>{frame.label}</strong>{cluster && <small>{cluster.label}</small>}</figcaption>
        <svg viewBox={`${frame.left} ${frame.top} ${Math.max(1, frame.width)} ${Math.max(1, frame.height)}`} role="img" aria-label={`Systemrahmen ${frame.label}, ausgewählt: ${selected.map(node => node.name).join(', ')}`}>
          <rect x={frame.left + 2} y={frame.top + 2} width={Math.max(1, frame.width - 4)} height={Math.max(1, frame.height - 4)} rx="12" fill="#101820" stroke="#9a8446" />
          {buses.map(bus => <g key={bus.id} fill="none" stroke={busProfiles[bus.technology].color} strokeWidth="2">
            <title>{bus.name}</title><path d={bus.displayPath || bus.path} />
            {bus.branches.filter(branch => members.has(branch.nodeId)).map(branch => <path key={branch.portId} d={branch.displayPath || branch.path} />)}
          </g>)}
          {nodes.map(node => <g key={node.id}>
            <title>{node.name} · {kinds[node.kind]}{ids.has(node.id) ? ' · Ausgewählter Empfänger' : ''}</title>
            <rect x={node.x} y={node.y} width={node.width ?? 180} height={node.height ?? 100} rx="8" fill={ids.has(node.id) ? '#263622' : '#101923'} stroke={ids.has(node.id) ? '#a4e852' : '#7795a6'} strokeWidth={ids.has(node.id) ? 3 : 1.5} />
            <foreignObject x={node.x + 8} y={node.y + 8} width={Math.max(1, (node.width ?? 180) - 16)} height={Math.max(1, (node.height ?? 100) - 16)}>
              <div className={styles.nodeLabel}><small>{kinds[node.kind]}</small><strong>{node.name}</strong></div>
            </foreignObject>
          </g>)}
        </svg>
        <ul className={styles.members}>{nodes.map(node => <li key={node.id} className={ids.has(node.id) ? styles.selected : undefined}>{node.name}{ids.has(node.id) && <span> · Empfänger</span>}</li>)}</ul>
      </figure>;
    })}
  </div>;
}

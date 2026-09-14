"use client";

import { useId } from 'react';
import { diagramPositions, type AgentOutputEnvelope, type VisualizationRequest } from '../lib/agent/input-output';

function EvidenceTable({ view }: {view: VisualizationRequest}) {
  return <table><caption>{view.purpose}</caption><thead><tr>{view.columns.map((name, i) => <th key={i} scope="col">{name}</th>)}</tr></thead>
    <tbody>{view.rows.map((row, i) => <tr key={i}>{row.map((cell, j) => <td key={j}>{cell}</td>)}</tr>)}</tbody></table>;
}

function NetworkDiagram({ view }: {view: VisualizationRequest}) {
  const marker = useId().replaceAll(':', '');
  const positions = diagramPositions(view);
  const width = Math.max(400, ...[...positions.values()].map(p => p.x + 190));
  const height = Math.max(130, ...[...positions.values()].map(p => p.y + 90));
  return <><div className="engineering-output-scroll" tabIndex={0} aria-label="Netzwerkdiagramm, horizontal scrollbar">
    <svg width={width} height={height} role="img" aria-label={view.purpose}>
      <defs><marker id={marker} markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="var(--muted)" /></marker></defs>
      {view.relationships.map((edge, i) => {
        const a = positions.get(edge.source)!; const b = positions.get(edge.target)!;
        return <g key={i}><title>{edge.label}</title><path d={`M${a.x + 170},${a.y + 30} C${a.x + 195},${a.y + 30} ${b.x - 25},${b.y + 30} ${b.x},${b.y + 30}`} fill="none" stroke="var(--muted)" markerEnd={`url(#${marker})`} /></g>;
      })}
      {view.nodes.map(node => {const p = positions.get(node.id)!; return <g key={node.id} transform={`translate(${p.x},${p.y})`}>
        <title>{`${node.label} · ${node.object_type} · ${node.id}`}</title>
        <rect width="170" height="60" rx="6" fill="var(--surface-raised)" stroke="var(--border-strong)" />
        <text x="10" y="24" fill="var(--text)" fontSize="12">{node.label.length > 22 ? `${node.label.slice(0, 21)}…` : node.label}</text>
        <text x="10" y="44" fill="var(--muted)" fontSize="10">{node.object_type}</text>
      </g>;})}
    </svg></div><details><summary>Verbindungen als Tabelle</summary><table><thead><tr><th>Quelle</th><th>Beziehung</th><th>Ziel</th></tr></thead><tbody>
      {view.relationships.map((edge, i) => <tr key={i}><td>{view.nodes.find(n => n.id === edge.source)?.label}</td><td>{edge.label}</td><td>{view.nodes.find(n => n.id === edge.target)?.label}</td></tr>)}
    </tbody></table></details></>;
}

// Approved composition registry: outputs contain data, never CSS or executable UI.
const DesignSystemRegistry = {NETWORK_DIAGRAM: NetworkDiagram, TABLE: EvidenceTable};

export function EngineeringOutputs({ outputs, projectId }: {outputs: AgentOutputEnvelope[]; projectId: string}) {
  return <div className="engineering-outputs">{outputs.filter(output => output.project_ref === projectId).map(output => {
    const view = output.visualization;
    if (!view) return null;
    const Component = DesignSystemRegistry[view.visualization_type];
    return <section key={output.output_id} data-engineering-output={output.output_type}>
      <h4>{output.content}</h4>
      {output.status !== 'CURRENT' && <p role="status">Veralteter Nachweis – Modellstand erneut prüfen.</p>}
      {view.truncated && <p>Ausschnitt: {view.nodes.length || view.rows.length} von {view.total_objects} Objekten/Prüfungen. Weitere Beziehungen können ausgeblendet sein.</p>}
      <Component view={view} />
      <small>Modellrevision {view.source_revision.slice(0, 12)} · {output.evidence_refs.length} Routennachweise</small>
    </section>;
  })}</div>;
}

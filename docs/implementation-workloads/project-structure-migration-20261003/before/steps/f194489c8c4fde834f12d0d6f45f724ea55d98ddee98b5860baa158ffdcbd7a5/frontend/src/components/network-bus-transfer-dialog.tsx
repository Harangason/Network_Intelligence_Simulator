"use client";

import { useEffect, useRef, useState } from 'react';
import type { NetworkTopology, TopologyEdge } from '@/lib/topology';
import { busTransferTargets, transferableNodes } from '@/lib/network-bus-transfer';
import { previewNetworkAssignment, type NetworkAssignmentRequest, type NetworkAssignmentPreview } from '@/lib/workflow-api';

export function NetworkBusTransferDialog({ topology, edge, onClose, onApply }: {
  topology: NetworkTopology; edge: TopologyEdge; onClose: () => void;
  onApply: (request: NetworkAssignmentRequest) => Promise<void>;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const nodes = transferableNodes(topology, edge);
  const [nodeId, setNodeId] = useState(nodes.length === 1 ? nodes[0].id : '');
  const [targetId, setTargetId] = useState('');
  const [preview, setPreview] = useState<NetworkAssignmentPreview | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const sourceId = edge.physicalNetworkId ?? '';
  const source = topology.scene?.buses.find(b => b.id === sourceId);
  const targets = busTransferTargets(topology, sourceId, nodeId);
  const cluster = topology.scene?.clusters.find(c => c.memberIds.includes(nodeId));
  // Bind the returned preview to the exact selection, including the first render
  // after a user changes it, before the effect has invalidated old results.
  const selection = `${nodeId}:${sourceId}:${targetId}`;
  const [previewSelection, setPreviewSelection] = useState('');
  const ready = Boolean(preview && previewSelection === selection && !loading && !busy);
  useEffect(() => { const element = dialog.current; element?.showModal(); return () => element?.close(); }, []);
  useEffect(() => {
    const controller = new AbortController();
    setPreview(null); setError(''); setLoading(Boolean(nodeId && targetId));
    if (nodeId && targetId) previewNetworkAssignment({node_ids:[nodeId], target_kind:'bus', target_id:targetId, source_network_id:sourceId}, controller.signal)
      .then(result => { if (!controller.signal.aborted) { setPreview(result); setPreviewSelection(selection); } })
      .catch(reason => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Vorschau fehlgeschlagen.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [nodeId, sourceId, targetId, selection, refresh]);
  async function apply() {
    if (!ready || !preview) return;
    setBusy(true); setError('');
    try {
      await onApply({node_ids:[nodeId], target_kind:'bus', source_network_id:sourceId, target_id:targetId, plan_token:preview.token});
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Das Umhängen konnte nicht gespeichert werden.'); setPreview(null);
    } finally { setBusy(false); }
  }
  return <dialog ref={dialog} className="net-assignment-dialog" aria-labelledby="bus-transfer-title" onCancel={event => {event.preventDefault(); if (!busy) onClose();}}>
    <header><div><span className="eyebrow">PHYSISCHER BUS</span><h2 id="bus-transfer-title">An anderen Bus umhängen</h2></div><button type="button" aria-label="Buswechsel schließen" disabled={busy} onClick={onClose}>×</button></header>
    <p>Aktueller Bus: <strong>{source?.name ?? sourceId}</strong>{cluster ? <> · Cluster: <strong>{cluster.label}</strong></> : null}</p>
    <p>Der gewählte Geräteanschluss wechselt auf den Zielbus. Systemzuordnung und interne Busse bleiben erhalten.</p>
    <div className="net-assignment-fields">
      <label htmlFor="bus-transfer-device">Gerät<select id="bus-transfer-device" disabled={busy} value={nodeId} onChange={event => {setNodeId(event.target.value); setTargetId('');}}><option value="">Bitte auswählen …</option>{nodes.map(n => <option value={n.id} key={n.id}>{n.name}</option>)}</select></label>
      <label htmlFor="bus-transfer-target">Zielbus im selben Cluster<select id="bus-transfer-target" disabled={busy || !nodeId} value={targetId} onChange={event => setTargetId(event.target.value)}><option value="">Bitte auswählen …</option>{targets.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}</select></label>
    </div>
    {nodeId && !targets.length && <p>Kein anderer kompatibler Bus vorhanden. Lokale Geräte benötigen einen Zielbus im selben Systemrahmen; der Bustyp muss übereinstimmen.</p>}
    {loading && <p role="status">Anschlüsse, Nachrichtenkennungen und Kommunikationspfade werden geprüft …</p>}
    {error && <div><p role="alert" className="net-assignment-error">{error}</p><button disabled={busy || loading} type="button" onClick={() => setRefresh(n => n + 1)}>Vorschau aktualisieren</button></div>}
    {preview && previewSelection === selection && <div role="status"><ul>{preview.connections.map((c,i) => <li key={i}><strong>{c.device}</strong>: {source?.name ?? c.from} → {targets.find(b => b.id === targetId)?.name ?? c.to}</li>)}</ul><p>{preview.messages} {preview.messages === 1 ? 'Nachricht' : 'Nachrichten'} · {preview.routes} {preview.routes === 1 ? 'Route' : 'Routen'}. Anschlüsse und gespeicherte Ansicht werden gemeinsam aktualisiert. Betroffene Routen müssen anschließend erneut freigegeben werden.</p></div>}
    <footer><button type="button" disabled={busy} onClick={onClose}>Zurück zur Verbindung</button><button type="button" className="button primary" disabled={!ready} onClick={() => void apply()}>{busy ? 'Wird umgehängt …' : 'Auf Zielbus umhängen'}</button></footer>
  </dialog>;
}

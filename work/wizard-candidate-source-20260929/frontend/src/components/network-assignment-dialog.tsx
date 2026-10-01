"use client";

import { useEffect, useRef, useState } from 'react';
import type { NetworkTopology } from '@/lib/topology';
import { alphabeticalTargets } from '@/lib/network-selection';
import { previewNetworkAssignment, type NetworkAssignmentRequest, type NetworkAssignmentPreview } from '@/lib/workflow-api';
import { networkLabel } from '@/lib/network-names';

export function NetworkAssignmentDialog({topology, nodeIds, onClose, onApply}: {
  topology: NetworkTopology; nodeIds: string[]; onClose: () => void;
  onApply: (request: NetworkAssignmentRequest) => Promise<void>;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [kind, setKind] = useState<'cluster'|'frame'>(()=>topology.nodes.some(n=>nodeIds.includes(n.id) && n.kind==='ecu')?'cluster':'frame');
  const [targetId, setTargetId] = useState('');
  const [preview, setPreview] = useState<NetworkAssignmentPreview|null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const selected = topology.nodes.filter(n=>nodeIds.includes(n.id));
  const targets = alphabeticalTargets<{id:string;label:string}>(kind==='cluster' ? topology.scene?.clusters??[] : (topology.scene?.frames??[]).filter(f=>!nodeIds.includes(f.id) && topology.nodes.find(n=>n.id===f.id)?.kind==='ecu'));
  useEffect(()=>{const element=dialog.current; element?.showModal();return()=>element?.close();},[]);
  useEffect(()=>{
    const controller = new AbortController();
    setPreview(null);setError('');setLoading(Boolean(targetId));
    if (targetId) previewNetworkAssignment({node_ids:nodeIds,target_kind:kind,target_id:targetId},controller.signal)
      .then(result=>{if(!controller.signal.aborted)setPreview(result);})
      .catch(reason=>{if(!controller.signal.aborted)setError(reason instanceof Error?reason.message:'Vorschau konnte nicht erstellt werden.');})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return()=>controller.abort();
  },[nodeIds,kind,targetId,refresh]);
  async function apply() {
    if (!preview || busy) return;
    setBusy(true);setError('');
    try {await onApply({node_ids:nodeIds,target_kind:kind,target_id:targetId,plan_token:preview.token});onClose();}
    catch(reason){setError(reason instanceof Error?reason.message:'Die Zuordnung konnte nicht gespeichert werden.');setPreview(null);}
    finally{setBusy(false);}
  }
  return <dialog ref={dialog} className="net-assignment-dialog" aria-labelledby="network-assignment-title" onCancel={event=>{event.preventDefault();if(!busy)onClose();}}>
    <header><div><span className="eyebrow">NETZWERK-ZUORDNUNG</span><h2 id="network-assignment-title">Zuordnung korrigieren</h2></div><button type="button" aria-label="Zuordnung schließen" disabled={busy} onClick={onClose}>×</button></header>
    <p>{selected.length} {selected.length===1?'Gerät':'Geräte'} markiert. Zugehörige Inhalte eines markierten Steuergeräts werden mitgenommen.</p>
    <div className="net-assignment-fields">
      <label>Zieltyp<select value={kind} disabled={busy} onChange={event=>{setKind(event.target.value as 'cluster'|'frame');setTargetId('');}}><option value="cluster">Cluster</option><option value="frame">Systemrahmen</option></select></label>
      <label>{kind==='cluster'?'Zielcluster':'Zielsystemrahmen'}<select value={targetId} disabled={busy} onChange={event=>setTargetId(event.target.value)}><option value="">Bitte auswählen …</option>{targets.map(t=><option value={t.id} key={t.id}>{t.label}</option>)}</select></label>
    </div>
    {loading && <p role="status">Zuordnung und Kommunikationspfade werden geprüft …</p>}
    {error && <div><p role="alert" className="net-assignment-error">{error}</p><button type="button" disabled={busy||loading} onClick={()=>setRefresh(value=>value+1)}>Vorschau aktualisieren</button></div>}
    {preview ? <>
      <table><caption>Änderungen an der Zugehörigkeit</caption><thead><tr><th>Gerät</th><th>Bisher</th><th>Nach Bestätigung</th></tr></thead><tbody>{alphabeticalTargets(preview.members.map(m=>({...m,label:m.name}))).map(m=><tr key={m.id}><td>{m.name}</td><td>{m.from_cluster}<small>{m.from_frame}</small></td><td>{m.to_cluster}<small>{m.to_frame}</small></td></tr>)}</tbody></table>
      <ul>{preview.connections.map((connection,index)=><li key={index}><strong>{connection.device}</strong>: {networkLabel(connection.from)} → {networkLabel(connection.to)} ({connection.technology.replaceAll('_','-')})</li>)}</ul>
      <p>{preview.routes} Routen und {preview.messages} Nachrichten werden abgeglichen. {preview.new_objects>0?`${preview.new_objects} benötigte Modellobjekte werden ergänzt. `:''}{preview.new_commands>0?`${preview.new_commands} ${preview.new_commands===1?'Befehlsnachricht wird':'Befehlsnachrichten werden'} für den neuen Eigentümer übernommen. `:''}{preview.new_routes>0?`${preview.new_routes} gemeinsame Befehlsrouten werden für die markierten Empfänger aufgeteilt. `:''}Die Änderung wird nur mit gültigen Kommunikationspfaden gespeichert. Betroffene Routen stehen anschließend erneut zur Freigabe bereit.</p>
    </> : !loading && !error ? <ul>{selected.map(n=><li key={n.id}>{n.name}</li>)}</ul> : null}
    <footer><button type="button" disabled={busy} onClick={onClose}>Abbrechen</button><button className="button primary" type="button" disabled={!preview||loading||busy} onClick={()=>void apply()}>{busy?'Zuordnung wird übernommen …':'Zuordnung und Verbindungen übernehmen'}</button></footer>
  </dialog>;
}

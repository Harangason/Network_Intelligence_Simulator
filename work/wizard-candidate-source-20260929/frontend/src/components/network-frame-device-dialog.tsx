"use client";

import { useEffect, useRef, useState, type FormEvent } from 'react';
import { createPortal } from 'react-dom';
import type { FrameDeviceRequest } from '@/lib/workflow-api';

const kinds = [{id: 'ecu', label: 'ECU'}, {id: 'sensor', label: 'Sensor'}, {id: 'actuator', label: 'Aktor'}] as const;

export function NetworkFrameDeviceDialog({frame, onClose, onCreate}: {
  frame: {id: string; label: string}; onClose: () => void;
  onCreate: (request: FrameDeviceRequest) => Promise<void>;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const submitting = useRef(false);
  const [kind, setKind] = useState<FrameDeviceRequest['kind']>('ecu');
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    event.stopPropagation();
    if (submitting.current || !name.trim()) return;
    submitting.current = true;
    setBusy(true);
    setError('');
    try {
      await onCreate({frame_id: frame.id, kind, name: name.trim()});
      onClose();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Das Gerät konnte nicht angelegt werden.');
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }
  if (typeof document === 'undefined') return null;
  return createPortal(<dialog ref={dialog} className="net-assignment-dialog net-frame-device-dialog" aria-labelledby="frame-device-title"
    onCancel={event => {event.preventDefault(); if (!submitting.current) onClose();}}>
    <form onSubmit={submit}>
      <header><div><span className="eyebrow">SYSTEMRAHMEN · {frame.label}</span><h2 id="frame-device-title">Gerät hinzufügen</h2></div>
        <button type="button" aria-label="Dialog schließen" disabled={busy} onClick={onClose}>×</button></header>
      <div className="net-frame-device-kinds" role="group" aria-label="Gerätetyp">
        {kinds.map(option => <button key={option.id} type="button" aria-pressed={kind === option.id}
          className={kind === option.id ? 'primary' : ''} disabled={busy} onClick={() => {setKind(option.id); setError('');}}>+ {option.label}</button>)}
      </div>
      <label className="net-frame-device-name">Gerätename<input autoFocus required maxLength={160} value={name} disabled={busy}
        placeholder="Eindeutiger Name" onChange={event => {setName(event.target.value); setError('');}} /></label>
      <p>Das Gerät wird als Entwurf im Systemrahmen „{frame.label}“ gespeichert. Anschlüsse und Gerätedetails kannst du anschließend ergänzen.</p>
      {error && <p className="net-assignment-error" role="alert">{error}</p>}
      <footer><button type="button" disabled={busy} onClick={onClose}>Abbrechen</button>
        <button className="primary" type="submit" disabled={busy || !name.trim()}>{busy ? 'Wird angelegt …' : 'Gerät anlegen'}</button></footer>
    </form>
  </dialog>, document.body);
}

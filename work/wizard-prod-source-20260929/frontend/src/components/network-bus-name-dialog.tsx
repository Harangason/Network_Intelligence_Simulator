"use client";

import {useEffect, useRef, useState} from 'react';

export function NetworkBusNameDialog({name, onSave, onClose}: {
  name: string; onSave: (name: string) => Promise<void>; onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const pending = useRef(false);
  const [value, setValue] = useState(name);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { dialog.current?.showModal(); }, []);
  async function save() {
    if (pending.current || !value.trim()) return;
    pending.current = true;
    setSaving(true); setError('');
    try { await onSave(value.trim()); onClose(); }
    catch (error) { setError(error instanceof Error ? error.message : 'Der Busname konnte nicht gespeichert werden.'); }
    finally { pending.current = false; setSaving(false); }
  }
  return <dialog ref={dialog} className="net-rename-dialog net-bus-name-dialog" aria-labelledby="net-bus-name-title"
    onCancel={event => {event.preventDefault(); if (!saving) onClose();}}>
    <header><div><p className="eyebrow">Physischer Bus</p><h2 id="net-bus-name-title">Bus umbenennen</h2></div>
      <button type="button" aria-label="Dialog schließen" disabled={saving} onClick={onClose}>×</button></header>
    <label><span>Busname</span><input autoFocus aria-describedby="net-bus-name-hint" maxLength={120} value={value} disabled={saving}
      onChange={event => setValue(event.target.value)} onKeyDown={event => {
        if (event.key === 'Enter') {event.preventDefault(); event.stopPropagation(); void save();}
      }} /></label>
    <p id="net-bus-name-hint" className="net-bus-name-hint">Dieser Name wird auf der Buslinie angezeigt.</p>
    {error && <p className="notice error net-bus-name-error" role="alert">{error}</p>}
    <footer><button type="button" className="button secondary" disabled={saving} onClick={onClose}>Abbrechen</button>
      <button type="button" className="button primary" disabled={saving || !value.trim()} onClick={() => void save()}>{saving ? 'Wird gespeichert …' : 'Speichern'}</button></footer>
  </dialog>;
}

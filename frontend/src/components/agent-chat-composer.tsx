"use client";

import { useEffect, useRef, useState, type RefObject } from 'react';
import { CHAT_DOCUMENT_ACCEPT, MAX_CHAT_ATTACHMENTS, MAX_CHAT_FILE_BYTES, validateChatAttachment, type ChatAttachment } from '@/lib/agent/chat-attachments';

export function AgentChatComposer({ input, setInput, inputRef, ready, busy, projectId, onSubmit }: {
  input: string; setInput: (value: string) => void; inputRef: RefObject<HTMLTextAreaElement | null>;
  ready: boolean; busy: boolean; projectId: string; onSubmit: (text: string, files: ChatAttachment[]) => void;
}) {
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [reading, setReading] = useState(false);
  const [error, setError] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);
  const requestRef = useRef<AbortController | null>(null);
  useEffect(() => () => requestRef.current?.abort(), []);

  async function readFiles(files: File[]) {
    if (!files.length || requestRef.current) return;
    setError('');
    if (files.length + attachments.length > MAX_CHAT_ATTACHMENTS) { setError('Höchstens vier Dokumente pro Nachricht.'); return; }
    const controller = new AbortController();
    requestRef.current = controller;
    setReading(true);
    const failures: string[] = [];
    try {
      for (const file of files) {
        try {
          if (file.size > MAX_CHAT_FILE_BYTES) throw new Error('Höchstens 5 MB pro Datei.');
          const body = new FormData(); body.append('file', file);
          const response = await fetch('/api/engineering/agent/attachments/preview', {
            method: 'POST', headers: { 'X-Project-ID': projectId }, body,
            signal: AbortSignal.any([controller.signal, AbortSignal.timeout(30_000)]),
          });
          const result = await response.json().catch(() => ({}));
          if (!response.ok) throw new Error(result.error || 'Das Dokument konnte nicht gelesen werden.');
          const attachment = validateChatAttachment(result);
          setAttachments(current => [...current, attachment]);
        } catch (error) {
          if (controller.signal.aborted) return;
          failures.push(`${file.name}: ${error instanceof Error ? error.message : 'Lesen fehlgeschlagen.'}`);
        }
      }
      setError(failures.join('\n'));
    } finally {
      requestRef.current = null;
      if (!controller.signal.aborted) setReading(false);
    }
  }

  return <form className="eng-agent-form eng-agent-composer" onSubmit={event => {
    event.preventDefault();
    if (!ready || busy || reading || (!input.trim() && !attachments.length)) return;
    onSubmit(input.trim() || 'Bitte prüfe die angehängten Dokumente.', attachments);
    setAttachments([]); setError('');
  }}>
    <div className="eng-agent-attachments" aria-live="polite">
      {attachments.map((file, index) => <div className="eng-agent-attachment" key={`${index}:${file.name}`}>
        <details><summary>{file.name} · {file.text.length.toLocaleString('de-DE')} Zeichen{file.truncated ? ' · Auszug' : ''}</summary>
          {file.truncated && <p>Der Auszug enthält höchstens 16.000 Zeichen und bei PDFs höchstens 40 Seiten.</p>}
          <pre>{file.text}</pre>
        </details>
        <button type="button" aria-label={`${file.name} entfernen`} disabled={reading} onClick={() => setAttachments(current => current.filter((_, i) => i !== index))}>×</button>
      </div>)}
      {reading && <span>Datei wird gelesen …</span>}
      {error && <p className="notice error" role="alert">{error}</p>}
    </div>
    <textarea aria-label="Nachricht an den Engineering-Assistenten" ref={inputRef} rows={2} value={input}
      onChange={event => setInput(event.target.value)} placeholder="Deine Frage oder dein Auftrag …"
      onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
        event.preventDefault(); event.currentTarget.form?.requestSubmit();
      } }} />
    <div className="eng-agent-composer-actions">
      <input ref={fileRef} type="file" accept={CHAT_DOCUMENT_ACCEPT} multiple hidden aria-label="Dokumente auswählen"
        onChange={event => { void readFiles(Array.from(event.target.files ?? [])); event.target.value = ''; }} />
      <button className="button secondary" type="button" disabled={reading || attachments.length >= MAX_CHAT_ATTACHMENTS} onClick={() => fileRef.current?.click()}>+ Dokument</button>
      <button className="button primary" type="submit" disabled={!ready || busy || reading || (!input.trim() && !attachments.length)}>{busy ? 'Antwort läuft …' : 'Senden'}</button>
    </div>
    <small>PDF, Word, Text, DBC, ARXML · bis 4 Dateien à 5 MB · Umschalt+Enter: neue Zeile</small>
  </form>;
}

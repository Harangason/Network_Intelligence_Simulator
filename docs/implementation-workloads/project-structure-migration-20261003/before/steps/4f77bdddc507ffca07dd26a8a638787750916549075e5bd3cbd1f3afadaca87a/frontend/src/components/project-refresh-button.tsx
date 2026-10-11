"use client";

import Link from 'next/link';
import { useRef, useState } from 'react';
import { readActiveProjectId, withProjectParam } from '@/lib/user-settings';
import { clearWorkflowApiCaches } from '@/lib/workflow-api';
import { notifyWorkflowChanged } from './workflow-header';
import styles from './project-refresh-button.module.css';

type Finding = { severity: string; category: string; code: string; message: string; recommendation?: string; object_name?: string; route_code?: string };
type Report = { project_id: string; project_name: string; error_count: number; warning_count: number; checked_routes: number; findings: Finding[] };
const categories: Record<string, string> = { engineering_model: 'Engineering-Modell', routing: 'Routing', network: 'Netzwerk', parameters: 'Parameter', capacity: 'Kapazität', timing: 'Timing', reliability: 'Zuverlässigkeit', synchronization: 'Synchronisation', addressing: 'Adressierung' };

export function ProjectRefreshButton({ disabled }: { disabled: boolean }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const inFlight = useRef(false);
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState('');
  async function refresh() {
    if (inFlight.current) return;
    inFlight.current = true;
    const project = readActiveProjectId();
    setBusy(true); setReport(null); setError('');
    dialog.current?.showModal();
    try {
      const response = await fetch('/api/engineering/workflow/refresh-project', { method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Project-ID': project }, body: '{}' });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Projektprüfung fehlgeschlagen.');
      if (readActiveProjectId() !== project || data.project_id !== project) throw new Error('Das aktive Projekt wurde gewechselt. Bitte das neue Projekt erneut prüfen.');
      setReport(data);
      clearWorkflowApiCaches();
      notifyWorkflowChanged();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Projektprüfung fehlgeschlagen.'); }
    finally { inFlight.current = false; setBusy(false); }
  }
  return <>
    <button className="topbar-command" disabled={disabled || busy} onClick={() => void refresh()} type="button"
      title="Aktuellen Projektstand prüfen, Berechnungen aktualisieren und Fehler melden">{busy ? 'Projekt wird geprüft …' : 'Projekt aktualisieren'}</button>
    <dialog ref={dialog} className={styles.dialog} aria-labelledby="project-refresh-title">
      <header><div><p className={styles.eyebrow}>Projektprüfung</p><h2 id="project-refresh-title">Projekt aktualisieren</h2></div>
        <button className="button secondary" type="button" aria-label="Projektprüfung schließen" onClick={() => dialog.current?.close()}>×</button></header>
      <div className={styles.body}>
        {busy && <p role="status">Modell und Routen prüfen, Kapazität und Timing neu berechnen, Preflight ausführen …</p>}
        {error && <p className={styles.error} role="alert">{error}</p>}
        {report && <>
          <strong>{report.project_name}</strong>
          <p role="status" className={report.error_count ? styles.error : undefined}>{report.error_count} Fehler · {report.warning_count} Warnungen · {report.checked_routes} aktuelle Routen geprüft</p>
          <p>Prüfungen und Berechnungen sind aktualisiert. Architektur, Parameter und Freigaben wurden nicht automatisch geändert.</p>
          {!report.findings.length && <p>Die Projektprüfung hat keine Fehler oder Warnungen gefunden.</p>}
          {Object.entries(categories).map(([category, label]) => {
            const findings = report.findings.filter(item => item.category === category);
            return findings.length > 0 && <details key={category} className={styles.group}>
              <summary>{label} · {findings.filter(item => item.severity === 'ERROR').length} Fehler · {findings.filter(item => item.severity === 'WARNING').length} Warnungen</summary>
              <ul>{findings.map((finding, index) => <li key={index}>
                <strong>{finding.severity === 'ERROR' ? 'Fehler' : finding.severity === 'WARNING' ? 'Warnung' : 'Hinweis'}{finding.route_code && ` · ${finding.route_code}`}{finding.object_name && ` · ${finding.object_name}`}</strong>
                <p>{finding.message}</p>{finding.recommendation && <p>{finding.recommendation}</p>}<small>{finding.code}</small>
              </li>)}</ul>
            </details>;
          })}
        </>}
      </div>
      <footer>{report && <Link className="button secondary" href={withProjectParam('/studio/validation', report.project_id)} onClick={() => dialog.current?.close()}>Prüfbericht öffnen</Link>}
        <button className="button primary" type="button" onClick={() => dialog.current?.close()}>Schließen</button></footer>
    </dialog>
  </>;
}

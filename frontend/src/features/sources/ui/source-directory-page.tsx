'use client';

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { MarketingShell, ProjectAwareLink } from '@/features/marketing/ui/marketing-shell';
import { expandBrowserProjectId, readActiveProjectId } from '@/features/settings/lib/user-settings';
import { displaySourceDate, sourceGroups } from '@/features/sources/lib/source-directory';
import type { SourceDirectory, SourceRow, SourceSort } from '@/features/sources/lib/source-directory';
import styles from '../../../app/sources/sources.module.css';

const columns: Array<{key: SourceSort; label: string}> = [
  {key: 'abbreviation', label: 'Kürzel · Bustyp'}, {key: 'technology', label: 'Name Bustyp'},
  {key: 'name', label: 'Quellenname'}, {key: 'url', label: 'Link'},
  {key: 'accessed_at', label: 'Datum des Abrufs'}, {key: 'rights', label: 'Veröffentlichung / Lizenz'},
  {key: 'license', label: 'Technikfreigabe'},
];

export default function SourcesPage() {
  return <Suspense fallback={<p role="status">Quellen werden geladen …</p>}><SourcesContent /></Suspense>;
}

function SourcesContent() {
  const searchParams = useSearchParams();
  const projectQuery = searchParams.get('project') ?? searchParams.get('project_id') ?? searchParams.get('projectId') ?? '';
  const [directory, setDirectory] = useState<SourceDirectory | null>(null);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<SourceSort>('abbreviation');
  const [descending, setDescending] = useState(false);
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<SourceRow | null>(null);
  const [licenseTechnology, setLicenseTechnology] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const licenseDialog = useRef<HTMLDialogElement>(null);
  const project = useRef('');
  const generation = useRef(0);
  const load = useCallback(async () => {
    const requestGeneration = ++generation.current;
    setError('');
    project.current = projectQuery ? expandBrowserProjectId(projectQuery) : readActiveProjectId();
    try {
      const response = await fetch('/api/technology-sources', {cache: 'no-store', headers: {'X-Project-ID': project.current}});
      const data = await response.json();
      if (requestGeneration !== generation.current) return;
      if (!response.ok) throw new Error(data.error || 'Quellen nicht erreichbar.');
      setDirectory(data);
    } catch (cause) { if (requestGeneration === generation.current) setError(cause instanceof Error ? cause.message : 'Quellen nicht erreichbar.'); }
  }, [projectQuery]);
  useEffect(() => {
    setDirectory(null); setSelected(null); setLicenseTechnology(''); setMessage(''); setBusy(false);
    dialog.current?.close(); licenseDialog.current?.close();
    void load();
    return () => { ++generation.current; };
  }, [load]);
  useEffect(() => { if (selected) dialog.current?.showModal(); }, [selected]);
  useEffect(() => { if (licenseTechnology) licenseDialog.current?.showModal(); }, [licenseTechnology]);
  const groups = useMemo(() => sourceGroups(directory?.sources ?? [], query, sort, descending, directory?.licenses), [directory, query, sort, descending]);
  const visible = groups.slice(page * 50, (page + 1) * 50);
  const matchingSources = new Set(groups.flatMap(group => group.sources.map(row => row.id))).size;
  const restricted = directory ? Object.entries(directory.licenses).filter(([, state]) => state.clearance_required) : [];
  function chooseSort(key: SourceSort) {
    setDescending(key === sort ? !descending : false); setSort(key); setPage(0);
  }
  async function submit(form: HTMLFormElement) {
    const submittedProject = project.current;
    setBusy(true); setMessage('');
    const data = new FormData(form);
    try {
      const response = await fetch('/api/technology-licenses', {method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-Project-ID': submittedProject},
        body: JSON.stringify({technology: licenseTechnology, issuer: data.get('issuer'), reference: data.get('reference'),
          scope_description: data.get('scope_description'), expires_on: data.get('expires_on') || null})});
      const result = await response.json();
      if (submittedProject !== project.current) return;
      if (!response.ok) throw new Error(result.error || 'Einreichung fehlgeschlagen.');
      setMessage(result.message); await load();
    } catch (cause) { if (submittedProject === project.current) setMessage(cause instanceof Error ? cause.message : 'Einreichung fehlgeschlagen.'); }
    finally { if (submittedProject === project.current) setBusy(false); }
  }
  return <MarketingShell><section className={styles.directory} aria-labelledby="source-title">
    <header className={styles.header}><div><p className="section-label">Wissen & Herkunft</p>
      <h1 id="source-title">Quellenverzeichnis</h1><p>Standards, Dokumentation und Implementierungsquellen – den jeweiligen Bustypen zugeordnet.</p></div>
      <ProjectAwareLink href="/studio?mode=parameters" className={styles.back}>Zu den Technologien ↗</ProjectAwareLink></header>
    <div className={styles.summary}><span><strong>{directory?.source_count ?? '—'}</strong> eindeutige Quellen</span>
      <span><strong>{directory?.technology_count ?? '—'}</strong> Verbindungstypen</span>
      <span>Lizenzprüfung: <strong>{displaySourceDate(directory?.rights_reviewed_at ?? null)}</strong></span></div>
    <p className={styles.note}>Hier werden Quellenangaben und Links veröffentlicht, keine Originaldokumente. Dokumentrechte, Implementierungsrechte und Zertifizierung sind getrennt. „Ungeklärt“ bedeutet keine erteilte Erlaubnis; ein öffentlicher Download allein genügt nicht.</p>
    <div className={styles.toolbar}><label htmlFor="source-search">Fuzzy-Suche<input id="source-search" type="search" placeholder="Bustyp, Quelle oder Herausgeber …" value={query}
      onChange={event => {setQuery(event.target.value); setPage(0);}} /></label>
      <span role="status">{groups.length} Bustypen · {matchingSources} Quellen</span><button type="button" onClick={() => {setQuery(''); setSort('abbreviation'); setDescending(false); setPage(0);}}>Zurücksetzen</button></div>
    {error && <div role="alert" className={styles.error}>{error} <button onClick={() => void load()}>Erneut laden</button></div>}
    {!directory && !error && <p role="status">Quellen werden geladen …</p>}
    {directory && <><div className={styles.tableWrap}><table className={styles.table}><caption className={styles.caption}>Ein Eintrag pro Bustyp; zugehörige Quellen aufklappen. Standardreihenfolge alphabetisch nach Bustyp. Spaltenköpfe sortieren Bustypen und deren Quellen.</caption>
      <thead><tr>{columns.map(column => <th key={column.key} scope="col" aria-sort={sort === column.key ? descending ? 'descending' : 'ascending' : 'none'}>
        <button type="button" onClick={() => chooseSort(column.key)}>{column.label} <span aria-hidden="true">{sort === column.key ? descending ? '↓' : '↑' : '↕'}</span></button></th>)}</tr></thead>
      <tbody>{visible.map(group => <tr key={group.technology.id} data-technology={group.technology.id}>
        <td><span className={styles.code}>{group.technology.abbreviation}</span></td>
        <td><strong className={styles.busName}>{group.technology.name}</strong></td>
        <td colSpan={4}><details className={styles.sourceGroup}>
          <summary aria-label={`Quellen für ${group.technology.abbreviation} anzeigen`}>
            <strong>{group.sources.length} {group.sources.length === 1 ? 'Quelle' : 'Quellen'} anzeigen</strong>
            {group.sources.length !== group.totalSourceCount && <small>von {group.totalSourceCount} Quellen für diesen Bustyp</small>}
            <small>Veröffentlichungs- und Lizenzhinweise bei den einzelnen Quellen</small>
          </summary>
          <table className={styles.sourceList} aria-label={`Quellen für ${group.technology.abbreviation}`}>
            <thead><tr><th scope="col">Quellenname</th><th scope="col">Link</th><th scope="col">Datum des Abrufs</th><th scope="col">Veröffentlichung / Lizenz</th></tr></thead>
            <tbody>{group.sources.map(row => <tr key={row.id}>
              <td><strong>{row.name}</strong><small>{row.publisher}</small></td>
              <td><a href={row.url} target="_blank" rel="noopener noreferrer" aria-label={`Quelle öffnen: ${row.name}`}>Quelle öffnen ↗</a></td>
              <td><time dateTime={row.accessed_at ?? undefined}>{displaySourceDate(row.accessed_at)}</time></td>
              <td><button type="button" className={row.rights.publication === 'CONDITIONAL' ? styles.conditional : styles.stop}
                onClick={() => setSelected(row)} aria-label={`Lizenzhinweis: ${row.name}`}><span aria-hidden="true">{row.rights.publication === 'CONDITIONAL' ? 'ⓘ' : '⛔'}</span> {row.rights.label}</button></td>
            </tr>)}</tbody>
          </table>
        </details></td>
        <td>{directory.licenses[group.technology.id]?.clearance_required
          ? <button className={styles.licenseStatus} onClick={() => {setMessage(''); setLicenseTechnology(group.technology.id);}}>
            {directory.licenses[group.technology.id].blocked ? '⚠ Gesperrt' : '✓ Freigegeben'} · {group.technology.abbreviation}</button>
          : <span className={styles.neutral}>Keine belegte NIS-Lizenzsperre</span>}</td>
      </tr>)}</tbody></table></div>
      {!groups.length && <p className={styles.empty}>Keine passenden Quellen. Versuche ein kürzeres Kürzel oder einen anderen Suchbegriff.</p>}
      <div className={styles.pagination}><button disabled={page === 0} onClick={() => setPage(page - 1)}>Zurück</button>
        <span>Seite {page + 1} von {Math.max(1, Math.ceil(groups.length / 50))} · 50 Bustypen pro Seite</span>
        <button disabled={(page + 1) * 50 >= groups.length} onClick={() => setPage(page + 1)}>Weiter</button></div>
      <section className={styles.licenses} aria-labelledby="license-title"><h2 id="license-title">Projektbezogene Technikfreigaben</h2>
        <p>Auswählen und Konfigurieren bleibt möglich. Eine gesperrte Technik kann erst nach geprüfter Freigabe ausgeführt werden. Dokumentweitergabe und Produktzertifizierung werden dadurch nicht freigegeben.</p>
        {restricted.map(([id, state]) => <article key={id}><div><strong>{id.replaceAll('_', ' ').toUpperCase()}</strong><span>{state.blocked ? '⚠ Ausführung gesperrt' : '✓ Projektfreigabe vorhanden'}</span>
          <p>{state.reason}</p></div><button onClick={() => {setMessage(''); setLicenseTechnology(id);}}>Nachweise & Freigabe</button></article>)}
      </section></>}
    <dialog ref={dialog} className={styles.dialog} onClose={() => setSelected(null)} aria-labelledby="rights-title">
      {selected && <><div className={styles.dialogHeader}><h2 id="rights-title">{selected.rights.label}</h2><button aria-label="Lizenzhinweis schließen" onClick={() => dialog.current?.close()}>✕</button></div>
        <h3>{selected.name}</h3><p>{selected.rights.explanation}</p>
        <p>Dokumentversion / Prüfgrundlage:</p><ul>{selected.revisions.slice(0, 8).map(revision => <li key={revision}>{revision}</li>)}</ul>
        <div className={styles.dialogActions}><a href={selected.url} target="_blank" rel="noopener noreferrer">Originalquelle öffnen ↗</a>
          {selected.rights.evidence_url && <a href={selected.rights.evidence_url} target="_blank" rel="noopener noreferrer">Lizenzbedingungen öffnen ↗</a>}</div></>}
    </dialog>
    <dialog ref={licenseDialog} className={styles.dialog} onClose={() => setLicenseTechnology('')} aria-labelledby="clearance-title">
      {licenseTechnology && directory && <><div className={styles.dialogHeader}><h2 id="clearance-title">Technikfreigabe · {licenseTechnology.replaceAll('_', ' ').toUpperCase()}</h2><button aria-label="Technikfreigabe schließen" onClick={() => licenseDialog.current?.close()}>✕</button></div>
        <p>{directory.licenses[licenseTechnology]?.reason}</p><p><strong>{directory.licenses[licenseTechnology]?.blocked ? 'Ausführung derzeit gesperrt.' : 'Für dieses Projekt freigegeben.'}</strong> Eine eingereichte Referenz bleibt bis zur Betreiberprüfung ungeprüft.</p>
        {directory.licenses[licenseTechnology]?.evidence_url && <a href={directory.licenses[licenseTechnology].evidence_url} target="_blank" rel="noopener noreferrer">Anforderungen beim Lizenzgeber ↗</a>}
        <ul>{directory.licenses[licenseTechnology]?.records.map(record => <li key={record.id}>{record.issuer} · {record.reference} · {record.status}{record.expires_on ? ` · bis ${displaySourceDate(record.expires_on)}` : ''}</li>)}</ul>
        <form onSubmit={event => {event.preventDefault(); void submit(event.currentTarget);}}><h3>Nachweis zur Prüfung einreichen</h3>
          <p>Nur Referenzen eintragen; keine Vertragsgeheimnisse, Lizenzschlüssel oder Originaldokumente. Der Betreiber prüft den Nachweis außerhalb dieser Ansicht.</p>
          <label>Lizenzgeber<input name="issuer" required maxLength={500} /></label>
          <label>Lizenz- / Vertragsreferenz<input name="reference" required maxLength={500} /></label>
          <label>Erlaubter Nutzungsumfang<textarea name="scope_description" required maxLength={500} /></label>
          <label>Ablaufdatum, falls vorhanden<input name="expires_on" type="date" /></label>
          <button disabled={busy} type="submit">{busy ? 'Wird eingereicht …' : 'Nachweis einreichen'}</button>
        </form>{message && <p role="status">{message}</p>}</>}
    </dialog>
  </section></MarketingShell>;
}

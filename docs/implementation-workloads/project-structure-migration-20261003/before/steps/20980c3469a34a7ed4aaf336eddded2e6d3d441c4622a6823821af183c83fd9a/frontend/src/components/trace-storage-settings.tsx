"use client";

import { useEffect, useRef, useState } from "react";
import { storageRequest, type StorageDirectories, type TraceStorageSettings } from "@/lib/trace-storage-api";

export function TraceStorageSettingsPanel({ project }: { project: string }) {
  const [settings, setSettings] = useState<TraceStorageSettings | null>(null);
  const [draft, setDraft] = useState("");
  const [browser, setBrowser] = useState<StorageDirectories | null>(null);
  const [busy, setBusy] = useState(true);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const requestController = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    requestController.current = controller;
    storageRequest<TraceStorageSettings>(project, "settings", "GET", undefined, controller.signal)
      .then((value) => { if (!controller.signal.aborted) { setSettings(value); setDraft(value.path); } })
      .catch((reason) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Speicherpfad konnte nicht geladen werden."); })
      .finally(() => { if (!controller.signal.aborted) setBusy(false); });
    return () => { requestController.current?.abort(); };
  }, [project]);

  async function perform(action: (signal: AbortSignal) => Promise<void>) {
    requestController.current?.abort();
    const controller = new AbortController();
    requestController.current = controller;
    setBusy(true); setError(""); setMessage("");
    try { await action(controller.signal); }
    catch (reason) { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Speicheraktion fehlgeschlagen."); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }

  function browse(path = draft) {
    void perform(async (signal) => {
      const value = await storageRequest<StorageDirectories>(project, `directories?path=${encodeURIComponent(path)}`, "GET", undefined, signal);
      if (!signal.aborted) setBrowser(value);
    });
  }

  function save(path: string | null) {
    void perform(async (signal) => {
      const value = await storageRequest<TraceStorageSettings>(project, "settings", "PUT", { path }, signal);
      if (signal.aborted) return;
      setSettings(value); setDraft(value.path); setBrowser(null);
      setMessage("Speicherpfad gespeichert. Neue Läufe verwenden diesen Ordner; vorhandene und bereits gestartete Läufe bleiben unverändert.");
    });
  }

  return <section className="panel settings-panel trace-storage-panel" aria-labelledby="trace-storage-heading" aria-busy={busy}>
    <div className="panel-heading"><div><p className="eyebrow">Simulation · Projekt {project}</p><h2 id="trace-storage-heading">Speicherort für Traces und Ergebnisse</h2></div></div>
    <p id="trace-storage-help">Gilt für neue Läufe dieses Projekts. Jeder Lauf erhält einen eigenen Unterordner. Bestehende Dateien werden nicht verschoben oder gelöscht.</p>
    <label htmlFor="trace-storage-path"><strong>Speicherpfad</strong></label>
    <div className="settings-project-control">
      <input id="trace-storage-path" aria-describedby="trace-storage-help" value={draft} disabled={busy || !settings} spellCheck={false} onChange={(event) => { setDraft(event.target.value); setMessage(""); setError(""); }} />
      <button className="button secondary" type="button" disabled={busy || !settings} onClick={() => browse()}>Ordner auswählen</button>
    </div>
    {settings && <p className="trace-storage-current">Aktiv: <code>{settings.path}</code>{settings.path !== settings.resolved_path && <><br />Backend: <code>{settings.resolved_path}</code></>}</p>}
    {settings?.container && <details className="trace-storage-container"><summary>Windows-Ordner im Docker-Betrieb verwenden</summary>
      <p>{settings.host_folder_connected ? "Ein Host-Ordner ist eingebunden. Er steht in der Ordnerauswahl zur Verfügung." : "Aktuell ist das interne Docker-Volume verfügbar. Ein beliebiger Windows-Pfad ist im Container nicht automatisch erreichbar."}</p>
      <p>Für einen eigenen Windows-Ordner: NETWORKIS_TRACE_HOST_PATH auf den vorhandenen Ordner setzen und die mitgelieferte docker-compose.trace-storage.yml zusätzlich zur docker-compose.networkis.yml starten. Danach den Ordner hier auswählen. Der einmalige Container-Neustart sollte erst nach Ende laufender Simulationen erfolgen.</p>
    </details>}
    {browser && <div className="trace-storage-browser" role="group" aria-label="Speicherordner auswählen">
      <strong>Geöffneter Ordner</strong><code>{browser.path}</code>
      <div className="trace-storage-actions">{settings?.roots.map((root) => <button className="button secondary" type="button" key={root} disabled={busy} onClick={() => browse(root)}>{root}</button>)}</div>
      {browser.parent && <button className="button secondary" type="button" disabled={busy} onClick={() => browse(browser.parent!)}>Übergeordneter Ordner</button>}
      <div className="trace-storage-directory-list">{browser.directories.map((directory) => <button className="button secondary" type="button" disabled={busy} key={directory.path} onClick={() => browse(directory.path)}>{directory.name}</button>)}</div>
      {browser.directories.length === 0 && <p>Keine Unterordner vorhanden.</p>}
      {browser.truncated && <p>Die Anzeige ist auf 200 Unterordner begrenzt. Weitere Pfade können direkt eingegeben werden.</p>}
      <div className="trace-storage-actions"><button className="button" type="button" disabled={busy} onClick={() => { setDraft(browser.path); setBrowser(null); setMessage("Ordner ausgewählt. Zum Übernehmen bitte Speicherpfad speichern."); }}>Diesen Ordner auswählen</button>
      <button className="button secondary" type="button" disabled={busy} onClick={() => setBrowser(null)}>Auswahl schließen</button></div>
    </div>}
    <div className="trace-storage-actions">
      <button className="button secondary" type="button" disabled={busy || !draft.trim()} onClick={() => void perform(async (signal) => {
        const result = await storageRequest<{ exists: boolean; free_bytes: number }>(project, "validate", "POST", { path: draft }, signal);
        if (!signal.aborted) setMessage(`Schreibprüfung erfolgreich. ${(result.free_bytes / 1024 ** 3).toLocaleString("de-DE", { maximumFractionDigits: 1 })} GiB frei.${result.exists ? "" : " Der neue Ordner wird beim Speichern angelegt."}`);
      })}>Pfad prüfen</button>
      <button className="button" type="button" disabled={busy || !settings || !draft.trim() || draft === settings.path} onClick={() => save(draft)}>Speicherpfad speichern</button>
      <button className="button secondary" type="button" disabled={busy || !settings || settings.is_default} onClick={() => save(null)}>Standardpfad verwenden</button>
      {!settings && !busy && <button className="button secondary" type="button" onClick={() => void perform(async (signal) => {
        const value = await storageRequest<TraceStorageSettings>(project, "settings", "GET", undefined, signal);
        if (!signal.aborted) { setSettings(value); setDraft(value.path); }
      })}>Erneut laden</button>}
    </div>
    {busy && <p role="status">Speicher-Einstellungen werden verarbeitet …</p>}
    {message && <p role="status" className="settings-format-message">{message}</p>}
    {error && <p role="alert" className="trace-storage-error">{error}</p>}
  </section>;
}

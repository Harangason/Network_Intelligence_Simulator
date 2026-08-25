"use client";

import Link from "next/link";
import { useState } from "react";
import { RuntimeStatus } from "@/components/runtime-status";
import { openProjectBundleFromFile, saveProjectBundleToFile } from "@/lib/project-file";
import { exportProjectBundle, importProjectBundle } from "@/lib/workflow-api";
import { normalizeProjectId, readUserSettings, writeUserSettings } from "@/lib/user-settings";
import { notifyWorkflowChanged } from "./workflow-header";

export function StudioTopbar() {
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [projectId, setProjectId] = useState("");
  const [busy, setBusy] = useState<"save" | "open" | "">("");
  const [message, setMessage] = useState("");

  function setActiveProject(nextProjectId: string) {
    writeUserSettings({ ...readUserSettings(), activeProject: normalizeProjectId(nextProjectId) });
    notifyWorkflowChanged();
  }

  async function saveProject(targetProjectId?: string, forceChoose = false) {
    setBusy("save");
    setMessage("");
    try {
      const target = targetProjectId ? normalizeProjectId(targetProjectId) : undefined;
      const bundle = await exportProjectBundle(target);
      const saved = await saveProjectBundleToFile(bundle, { forceChoose });
      setActiveProject(bundle.project_id);
      setSaveDialogOpen(false);
      setMessage(`Gespeichert: ${saved.fileName}`);
    } catch (caught) {
      if ((caught as { name?: string }).name !== "AbortError") {
        setMessage(caught instanceof Error ? caught.message : "Projekt konnte nicht gespeichert werden.");
      }
    } finally {
      setBusy("");
    }
  }

  async function handleSave() {
    const current = readUserSettings().activeProject;
    if (current === "default") {
      setProjectId(`network-project-${new Date().toISOString().slice(0, 10)}`);
      setSaveDialogOpen(true);
      return;
    }
    await saveProject();
  }

  async function handleOpen() {
    setBusy("open");
    setMessage("");
    try {
      const { bundle } = await openProjectBundleFromFile();
      const imported = await importProjectBundle(bundle);
      setActiveProject(imported.project_id);
      setMessage(`Geöffnet: ${imported.project_id}`);
    } catch (caught) {
      if ((caught as { name?: string }).name !== "AbortError") {
        setMessage(caught instanceof Error ? caught.message : "Projekt konnte nicht geöffnet werden.");
      }
    } finally {
      setBusy("");
    }
  }

  return (
    <>
      <header className="topbar">
        <Link className="brand" href="/">
          <span className="brand-mark" aria-hidden="true">CS</span>
          <div>
            <strong>Communication Simulator</strong>
            <span>Network trace studio</span>
          </div>
        </Link>
        <div className="topbar-actions">
          {message && <span className="project-file-message" role="status">{message}</span>}
          <button className="topbar-command" disabled={Boolean(busy)} onClick={() => void handleSave()} type="button">Speichern</button>
          <button className="topbar-command" disabled={Boolean(busy)} onClick={() => void handleOpen()} type="button">Öffnen</button>
          <Link className="topbar-link" href="/studio/settings">Einstellungen</Link>
          <RuntimeStatus />
        </div>
      </header>

      {saveDialogOpen && (
        <div className="project-dialog-backdrop" role="presentation">
          <section aria-labelledby="project-save-title" aria-modal="true" className="project-dialog" role="dialog">
            <div>
              <p className="eyebrow">Projektablage</p>
              <h2 id="project-save-title">Projekt anlegen und Speicherort wählen</h2>
              <p>Die Projektdatei enthält Workflow, Engineering-Daten, Analysen, Simulationen und Governance-Historie.</p>
            </div>
            <label>
              <span>Projekt-ID</span>
              <input autoFocus onChange={(event) => setProjectId(event.target.value)} value={projectId} />
            </label>
            <div className="project-dialog-actions">
              <button className="button secondary" disabled={busy === "save"} onClick={() => setSaveDialogOpen(false)} type="button">Abbrechen</button>
              <button className="button primary" disabled={busy === "save" || !projectId.trim()} onClick={() => void saveProject(projectId, true)} type="button">Speicherort wählen</button>
            </div>
          </section>
        </div>
      )}
    </>
  );
}

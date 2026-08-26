"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { openProjectBundleFromFile, saveProjectBundleToFile } from "@/lib/project-file";
import { exportProjectBundle, importProjectBundle, resetProjectWorkspace } from "@/lib/workflow-api";
import { normalizeProjectId, readUserSettings, writeUserSettings } from "@/lib/user-settings";
import { notifyWorkflowChanged } from "./workflow-header";

type ProjectActionsProps = {
  className?: string;
  showMessage?: boolean;
};

export function ProjectActions({ className = "project-actions", showMessage = true }: ProjectActionsProps) {
  const router = useRouter();
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [projectId, setProjectId] = useState("");
  const [busy, setBusy] = useState<"new" | "save" | "open" | "">("");
  const [message, setMessage] = useState("");

  function setActiveProject(nextProjectId: string) {
    writeUserSettings({ ...readUserSettings(), activeProject: normalizeProjectId(nextProjectId) });
    notifyWorkflowChanged();
  }

  function createProjectId() {
    const stamp = new Date().toISOString().replace(/[-:T.Z]/g, "").slice(0, 14);
    return `network-project-${stamp}`;
  }

  function notifyAgentAboutNewProject(nextProjectId: string) {
    const detail = { projectId: nextProjectId, createdAt: Date.now() };
    window.sessionStorage.removeItem("networkis:handled-agent-questionnaires");
    window.sessionStorage.removeItem("networkis:agent-project-brief");
    window.sessionStorage.setItem(
      "networkis:forced-agent-questionnaire",
      JSON.stringify({ key: `full:new-project:${nextProjectId}`, mode: "full", title: "Technische Vorgaben" }),
    );
    window.sessionStorage.setItem("networkis:pending-agent-new-project", JSON.stringify(detail));
    window.dispatchEvent(new CustomEvent("engineering-agent:new-project", { detail }));
  }

  async function handleNew() {
    setBusy("new");
    setMessage("");
    try {
      const nextProjectId = createProjectId();
      const reset = await resetProjectWorkspace(nextProjectId);
      setActiveProject(reset.project_id);
      notifyAgentAboutNewProject(reset.project_id);
      setMessage(`Neu: leerer Workspace ${reset.project_id}`);
      if (window.location.pathname === "/studio/engineering") {
        window.location.reload();
      } else {
        window.location.assign("/studio/engineering");
      }
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Neuer Workspace konnte nicht angelegt werden.");
    } finally {
      setBusy("");
    }
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
      const { bundle, fileName } = await openProjectBundleFromFile((status) => setMessage(status.message));
      setMessage(`Importiere ${fileName} in die Engineering-Datenbank ...`);
      const imported = await importProjectBundle(bundle);
      setActiveProject(imported.project_id);
      setMessage(`Geöffnet: ${imported.project_id}`);
      router.push("/studio");
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
      <div className={className}>
        {showMessage && message && <span className="project-file-message" role="status">{message}</span>}
        <button className="topbar-command" disabled={Boolean(busy)} onClick={() => void handleNew()} type="button">Neu</button>
        <button className="topbar-command" disabled={Boolean(busy)} onClick={() => void handleSave()} type="button">Speichern</button>
        <button className="topbar-command" disabled={Boolean(busy)} onClick={() => void handleOpen()} type="button">Öffnen</button>
      </div>

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

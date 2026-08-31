"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { clearEngineeringAgentHistory } from "@/lib/agent-chat-history";
import { openProjectBundleFromFile, saveProjectBundleToFile } from "@/lib/project-file";
import { exportProjectBundle, importProjectBundle, resetProjectWorkspace } from "@/lib/workflow-api";
import { normalizeProjectId, readUserSettings, writeUserSettings } from "@/lib/user-settings";
import {
  ENGINEERING_AGENT_PENDING_TASK_KEY,
  ENGINEERING_AGENT_PENDING_WIZARD_KEY,
  requestEngineeringAgentWizard,
} from "@/lib/agent-task-events";
import { notifyWorkflowChanged } from "./workflow-header";

type ProjectActionsProps = {
  className?: string;
  showMessage?: boolean;
};

export function ProjectActions({ className = "project-actions", showMessage = true }: ProjectActionsProps) {
  const router = useRouter();
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [clearDialogOpen, setClearDialogOpen] = useState(false);
  const [projectId, setProjectId] = useState("");
  const [busy, setBusy] = useState<"new" | "clear" | "save" | "open" | "">("");
  const [message, setMessage] = useState("");

  function setActiveProject(nextProjectId: string) {
    writeUserSettings({ ...readUserSettings(), activeProject: normalizeProjectId(nextProjectId) });
    notifyWorkflowChanged();
  }

  function createProjectId() {
    const stamp = new Date().toISOString().replace(/[-:T.Z]/g, "").slice(0, 17);
    return `network-project-${stamp}-${crypto.randomUUID().slice(0, 8)}`;
  }

  function notifyAgentAboutNewProject(nextProjectId: string) {
    window.sessionStorage.removeItem(ENGINEERING_AGENT_PENDING_TASK_KEY);
    requestEngineeringAgentWizard(nextProjectId, { dispatch: false });
  }

  async function handleNew() {
    setBusy("new");
    setMessage("");
    try {
      const nextProjectId = createProjectId();
      setActiveProject(nextProjectId);
      notifyAgentAboutNewProject(nextProjectId);
      setMessage(`Neu: leerer Workspace ${nextProjectId}`);
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

  async function handleClear() {
    setBusy("clear");
    setMessage("");
    try {
      const current = readUserSettings().activeProject;
      const nextProjectId = createProjectId();
      await resetProjectWorkspace(current);
      await clearEngineeringAgentHistory(current);
      setActiveProject(nextProjectId);
      setClearDialogOpen(false);
      window.sessionStorage.removeItem(ENGINEERING_AGENT_PENDING_TASK_KEY);
      window.sessionStorage.removeItem(ENGINEERING_AGENT_PENDING_WIZARD_KEY);
      window.sessionStorage.removeItem("networkis:forced-agent-questionnaire");
      window.sessionStorage.removeItem("networkis:handled-agent-questionnaires");
      window.sessionStorage.removeItem("networkis:agent-project-brief");
      window.sessionStorage.removeItem("networkis:pending-agent-new-project");
      setMessage(`Geleert: ${current} · Neuer Workspace: ${nextProjectId}`);
      window.location.reload();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Workspace konnte nicht geleert werden.");
    } finally {
      setBusy("");
    }
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
        <button className="topbar-command danger" disabled={Boolean(busy)} onClick={() => setClearDialogOpen(true)} type="button">Clear</button>
        <button className="topbar-command" disabled={Boolean(busy)} onClick={() => void handleSave()} type="button">Speichern</button>
        <button className="topbar-command" disabled={Boolean(busy)} onClick={() => void handleOpen()} type="button">Öffnen</button>
      </div>

      {clearDialogOpen && (
        <div className="project-dialog-backdrop" role="presentation">
          <section aria-labelledby="project-clear-title" aria-modal="true" className="project-dialog" role="dialog">
            <div>
              <p className="eyebrow">Workspace bereinigen</p>
              <h2 id="project-clear-title">Aktives Projekt leeren?</h2>
              <p>
                Das kanonische Modell, Routing, Vorschläge, Analysen, Simulationen und der Workflowstatus
                von <strong>{readUserSettings().activeProject}</strong> werden dauerhaft entfernt.
              </p>
            </div>
            <div className="project-dialog-actions">
              <button autoFocus className="button secondary" disabled={busy === "clear"} onClick={() => setClearDialogOpen(false)} type="button">Abbrechen</button>
              <button className="button danger" disabled={busy === "clear"} onClick={() => void handleClear()} type="button">
                {busy === "clear" ? "Wird geleert ..." : "Workspace leeren"}
              </button>
            </div>
          </section>
        </div>
      )}

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

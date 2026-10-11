"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import {
  ENGINEERING_AGENT_WIZARD_SESSION_EVENT,
  readEngineeringAgentWizardSession,
} from "@/lib/agent-task-events";
import { isUnexpectedProjectRevisionChange, projectRevisionRefreshMode } from "@/lib/project-sync";
import { readActiveProjectId } from "@/lib/user-settings";

/** Observe persisted revisions; never replace an open editor's draft. */
export function ProjectSyncNotice() {
  const pathname = usePathname();
  const [changed, setChanged] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const refreshMode = projectRevisionRefreshMode(pathname);

  function acceptProjectRevision() {
    if (refreshMode === "in-place") {
      window.dispatchEvent(new CustomEvent("workflow:changed"));
      setChanged(false);
      return;
    }
    window.location.reload();
  }

  useEffect(() => {
    let stopped = false;
    let pending = false;
    let project = "";
    let baseline = "";
    let localWrite = 0;
    const onWrite = () => { baseline = ""; localWrite++; };
    const poll = async () => {
      if (pending || document.visibilityState !== "visible") return;
      const projectId = readActiveProjectId();
      if (project !== projectId) {
        project = projectId;
        baseline = "";
        setChanged(false);
      }
      pending = true;
      const write = localWrite;
      try {
        const response = await fetch("/api/engineering/workflow/revision", {
          headers: { "X-Project-ID": projectId }, cache: "no-store", signal: AbortSignal.timeout(8000),
        });
        if (!response.ok) throw new Error("Projekt nicht erreichbar");
        const state = await response.json();
        if (stopped || projectId !== readActiveProjectId() || write !== localWrite) return;
        const revision = JSON.stringify([state.versions, state.edit_tokens]);
        const wizardSessionActive = Boolean(readEngineeringAgentWizardSession(projectId));
        if (isUnexpectedProjectRevisionChange({
          baseline,
          revision,
          localWriteUnchanged: write === localWrite,
          wizardSessionActive,
        })) setChanged(true);
        else if (wizardSessionActive) setChanged(false);
        baseline = revision;
        setUnavailable(false);
      } catch {
        if (!stopped) setUnavailable(true);
      } finally {
        pending = false;
      }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 5000);
    const onWizardSession = () => {
      baseline = "";
      if (readEngineeringAgentWizardSession(readActiveProjectId())) setChanged(false);
      void poll();
    };
    window.addEventListener("engineering:write-completed", onWrite);
    window.addEventListener(ENGINEERING_AGENT_WIZARD_SESSION_EVENT, onWizardSession);
    window.addEventListener("focus", poll);
    document.addEventListener("visibilitychange", poll);
    return () => {
      stopped = true;
      window.clearInterval(timer);
      window.removeEventListener("engineering:write-completed", onWrite);
      window.removeEventListener(ENGINEERING_AGENT_WIZARD_SESSION_EVENT, onWizardSession);
      window.removeEventListener("focus", poll);
      document.removeEventListener("visibilitychange", poll);
    };
  }, []);

  if (!changed && !unavailable) return null;
  return (
    <aside className="panel" role="status" style={{ position: "fixed", bottom: 16, left: 16, zIndex: 90, maxWidth: 520, padding: 16 }}>
      <strong>{unavailable ? "Projektverbindung unterbrochen" : "Neuer Projektstand verfügbar"}</strong>
      <p>{unavailable
        ? "Der gemeinsame Projektstand ist derzeit nicht erreichbar. Lokale Eingaben bleiben erhalten."
        : refreshMode === "in-place"
          ? "Das Projekt wurde außerhalb dieser Ansicht geändert. Der neue Stand kann übernommen werden, ohne Simulation, Trace oder lokale Einstellungen zu verwerfen."
          : "Das Projekt wurde außerhalb dieser Ansicht geändert. Lokale Eingaben bleiben bis zum Neuladen erhalten."}</p>
      {changed && (
        <div className="project-sync-actions">
          <button className="button secondary" onClick={acceptProjectRevision} type="button">
            {refreshMode === "in-place" ? "Projektstand übernehmen (Simulation bleibt erhalten)" : "Aktuellen Stand laden (verwirft ungespeicherte Eingaben)"}
          </button>
          <button className="button ghost" onClick={() => setChanged(false)} type="button">Später</button>
        </div>
      )}
    </aside>
  );
}

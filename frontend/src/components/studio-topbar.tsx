"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { EngineeringImportWizard } from "@/components/engineering-import-wizard";
import { ProjectActions } from "@/components/project-actions";
import { RuntimeStatus } from "@/components/runtime-status";
import {
  ENGINEERING_AGENT_WIZARD_SESSION_EVENT,
  readEngineeringAgentWizardSession,
  requestEngineeringAgentWizard,
  type EngineeringAgentWizardSession,
} from "@/lib/agent-task-events";
import {
  adoptActiveProjectFromUrl,
  ensureCurrentUrlProjectParam,
  readActiveProjectId,
  SETTINGS_EVENT,
  withProjectParam,
} from "@/lib/user-settings";

export function StudioTopbar({ initialProjectId = "" }: { initialProjectId?: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const [activeProjectId, setActiveProjectId] = useState(initialProjectId);
  const [wizardSession, setWizardSession] = useState<EngineeringAgentWizardSession | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [agentLogEnabled, setAgentLogEnabled] = useState(false);
  const [agentLogBusy, setAgentLogBusy] = useState(false);
  const syncWizardSession = useCallback(() => {
    setWizardSession(readEngineeringAgentWizardSession(readActiveProjectId()));
  }, []);

  useEffect(() => {
    const activeProject = adoptActiveProjectFromUrl() ?? readActiveProjectId();
    setActiveProjectId(activeProject);
    ensureCurrentUrlProjectParam(activeProject);
    syncWizardSession();
    const handleSettingsChanged = () => {
      const nextProjectId = readActiveProjectId();
      setActiveProjectId(nextProjectId);
      ensureCurrentUrlProjectParam(nextProjectId);
      syncWizardSession();
    };
    window.addEventListener(ENGINEERING_AGENT_WIZARD_SESSION_EVENT, syncWizardSession);
    window.addEventListener(SETTINGS_EVENT, handleSettingsChanged);
    window.addEventListener("storage", syncWizardSession);
    return () => {
      window.removeEventListener(ENGINEERING_AGENT_WIZARD_SESSION_EVENT, syncWizardSession);
      window.removeEventListener(SETTINGS_EVENT, handleSettingsChanged);
      window.removeEventListener("storage", syncWizardSession);
    };
  }, [syncWizardSession]);

  useEffect(() => {
    let active = true;
    fetch("/api/agent/diagnostics?agentLog=status", { cache: "no-store" })
      .then((response) => response.ok ? response.json() : null)
      .then((payload: { enabled?: boolean } | null) => {
        if (active) setAgentLogEnabled(payload?.enabled === true);
      })
      .catch(() => {
        if (active) setAgentLogEnabled(false);
      });
    return () => {
      active = false;
    };
  }, []);

  function returnToWizard() {
    if (!wizardSession) return;
    requestEngineeringAgentWizard(wizardSession.projectId);
    if (pathname !== "/studio/engineering") router.push(withProjectParam("/studio/engineering", wizardSession.projectId));
  }

  async function toggleAgentLogging() {
    if (agentLogBusy) return;
    setAgentLogBusy(true);
    try {
      const response = await fetch("/api/agent/diagnostics", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "agent-log",
          enabled: !agentLogEnabled,
          projectId: readActiveProjectId(),
          runId: "topbar",
        }),
      });
      if (!response.ok) throw new Error(`Logging konnte nicht geschaltet werden (${response.status}).`);
      const payload = await response.json() as { enabled?: boolean };
      setAgentLogEnabled(payload.enabled === true);
    } catch {
      setAgentLogEnabled(false);
    } finally {
      setAgentLogBusy(false);
    }
  }

  return (
    <>
      <header className="topbar">
        <Link className="brand" href={withProjectParam("/", activeProjectId)}>
          <span className="brand-mark" aria-hidden="true">CS</span>
          <div>
            <strong>Communication Simulator</strong>
            <span>Network trace studio</span>
          </div>
        </Link>
        <div className="topbar-wizard-slot">
          {wizardSession && (
            <button className="topbar-command engineering-wizard-return" onClick={returnToWizard} type="button">
              <span aria-hidden="true">←</span>
              Zurück zum Auftrag
            </button>
          )}
        </div>
        <div className="topbar-actions">
          <ProjectActions />
          <button
            aria-pressed={agentLogEnabled}
            className={`topbar-command topbar-log-toggle ${agentLogEnabled ? "active" : ""}`}
            disabled={agentLogBusy}
            onClick={() => void toggleAgentLogging()}
            title={agentLogEnabled ? "Agent-Event-Logging stoppen" : "Agent-Event-Logging starten"}
            type="button"
          >
            <span className="topbar-log-dot" aria-hidden="true" />
            {agentLogEnabled ? "Loggen aus" : "Loggen an"}
          </button>
          <button className="topbar-command" onClick={() => setImportOpen(true)} type="button">
            Importieren
          </button>
          <Link className="topbar-link" href={withProjectParam("/studio/settings", activeProjectId)}>Einstellungen</Link>
          <RuntimeStatus />
        </div>
      </header>
      {importOpen && <EngineeringImportWizard onClose={() => setImportOpen(false)} />}
    </>
  );
}

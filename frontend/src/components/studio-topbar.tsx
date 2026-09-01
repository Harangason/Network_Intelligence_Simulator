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
import { adoptActiveProjectFromUrl, readActiveProjectId, SETTINGS_EVENT } from "@/lib/user-settings";

export function StudioTopbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [wizardSession, setWizardSession] = useState<EngineeringAgentWizardSession | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [agentLogEnabled, setAgentLogEnabled] = useState(false);
  const [agentLogBusy, setAgentLogBusy] = useState(false);
  const syncWizardSession = useCallback(() => {
    setWizardSession(readEngineeringAgentWizardSession(readActiveProjectId()));
  }, []);

  useEffect(() => {
    adoptActiveProjectFromUrl();
    syncWizardSession();
    window.addEventListener(ENGINEERING_AGENT_WIZARD_SESSION_EVENT, syncWizardSession);
    window.addEventListener(SETTINGS_EVENT, syncWizardSession);
    window.addEventListener("storage", syncWizardSession);
    return () => {
      window.removeEventListener(ENGINEERING_AGENT_WIZARD_SESSION_EVENT, syncWizardSession);
      window.removeEventListener(SETTINGS_EVENT, syncWizardSession);
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
    if (pathname !== "/studio/engineering") router.push("/studio/engineering");
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
        <Link className="brand" href="/">
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
          <Link className="topbar-link" href="/studio/settings">Einstellungen</Link>
          <RuntimeStatus />
        </div>
      </header>
      {importOpen && <EngineeringImportWizard onClose={() => setImportOpen(false)} />}
    </>
  );
}

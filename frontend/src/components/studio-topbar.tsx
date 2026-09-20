"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { EngineeringImportWizard } from "@/components/engineering-import-wizard";
import { ProjectSyncNotice } from "@/components/project-sync-notice";
import { ProjectActions } from "@/components/project-actions";
import { RuntimeStatus } from "@/components/runtime-status";
import { StudioThemeControl } from "@/components/studio-theme-control";
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

  function returnToWizard() {
    if (!wizardSession) return;
    requestEngineeringAgentWizard(wizardSession.projectId);
    if (pathname !== "/studio/engineering") router.push(withProjectParam("/studio/engineering", wizardSession.projectId));
  }

  return (
    <>
      <ProjectSyncNotice />
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
          <button className="topbar-command" onClick={() => setImportOpen(true)} type="button">
            Importieren
          </button>
          <StudioThemeControl />
          <Link className="topbar-link" href={withProjectParam("/studio/settings", activeProjectId)}>Einstellungen</Link>
          <RuntimeStatus />
        </div>
      </header>
      {importOpen && <EngineeringImportWizard onClose={() => setImportOpen(false)} />}
    </>
  );
}

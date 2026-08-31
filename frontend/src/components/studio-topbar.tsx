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
import { readActiveProjectId, SETTINGS_EVENT } from "@/lib/user-settings";

export function StudioTopbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [wizardSession, setWizardSession] = useState<EngineeringAgentWizardSession | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const syncWizardSession = useCallback(() => {
    setWizardSession(readEngineeringAgentWizardSession(readActiveProjectId()));
  }, []);

  useEffect(() => {
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

  function returnToWizard() {
    if (!wizardSession) return;
    requestEngineeringAgentWizard(wizardSession.projectId);
    if (pathname !== "/studio/engineering") router.push("/studio/engineering");
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

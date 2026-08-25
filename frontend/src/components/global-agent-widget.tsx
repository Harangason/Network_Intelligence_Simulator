"use client";

import { useEffect, useState } from "react";
import { AgentChatCore } from "@/components/agent-chat-core";
import { WorkflowStatusOverview } from "@/components/workflow-status-overview";
import { readUserSettings, SETTINGS_EVENT, type UserSettings } from "@/lib/user-settings";

export function GlobalAgentWidget() {
  const [activeProject, setActiveProject] = useState("default");

  useEffect(() => {
    const initial = readUserSettings();
    setActiveProject(initial.activeProject);
    const update = (event: Event) => {
      const next = (event as CustomEvent<UserSettings>).detail;
      setActiveProject(next.activeProject);
    };
    window.addEventListener(SETTINGS_EVENT, update);
    return () => window.removeEventListener(SETTINGS_EVENT, update);
  }, []);

  return (
    <aside
      aria-label="Engineering-Assistent"
      className="agent-widget has-workflow-status"
    >
      <WorkflowStatusOverview />
      <div className="agent-widget-panel">
        <div className="agent-widget-header">
          <div>
            <p className="agent-widget-eyebrow">Engineering-Assistent</p>
            <strong>Agent</strong>
          </div>
        </div>

        <div className="agent-widget-body">
          <AgentChatCore compact key={activeProject} />
        </div>
      </div>
    </aside>
  );
}

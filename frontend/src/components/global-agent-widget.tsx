"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { AssistantGraphBubble } from "@/components/assistant";
import { AgentChatCore } from "@/components/agent-chat-core";
import { ENGINEERING_AGENT_TASK_EVENT } from "@/lib/agent-task-events";
import { readUserSettings, SETTINGS_EVENT, type UserSettings } from "@/lib/user-settings";

export function GlobalAgentWidget() {
  const [activeProject, setActiveProject] = useState("default");
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const isLandingPage = pathname === "/";

  useEffect(() => {
    const initial = readUserSettings();
    setActiveProject(initial.activeProject);
    setOpen(!isLandingPage && initial.openAgentOnStart);
    const update = (event: Event) => {
      const next = (event as CustomEvent<UserSettings>).detail;
      setActiveProject(next.activeProject);
    };
    const openForTask = () => setOpen(true);
    window.addEventListener(SETTINGS_EVENT, update);
    window.addEventListener(ENGINEERING_AGENT_TASK_EVENT, openForTask);
    return () => {
      window.removeEventListener(SETTINGS_EVENT, update);
      window.removeEventListener(ENGINEERING_AGENT_TASK_EVENT, openForTask);
    };
  }, [isLandingPage]);

  return (
    <aside
      aria-label="Engineering-Assistent"
      className={`agent-widget ${open ? "is-open" : "is-collapsed"}`}
    >
        {open ? (
          <div className="agent-widget-panel">
            <div className="agent-widget-header">
              <div>
                <p className="agent-widget-eyebrow">Engineering-Assistent</p>
                <strong>Agent</strong>
              </div>
              <button
                aria-label="Engineering-Assistent schließen"
                className="agent-widget-close"
                onClick={() => setOpen(false)}
                title="AI Assistant minimieren"
                type="button"
              >
                x
              </button>
            </div>

            <div className="agent-widget-body">
              <AgentChatCore compact key={activeProject} />
            </div>
          </div>
        ) : (
          <AssistantGraphBubble
            active={false}
            onClick={() => setOpen(true)}
            size={64}
            state="idle"
            title="AI Assistant öffnen"
          />
        )}
    </aside>
  );
}

"use client";

import { usePathname } from "next/navigation";
import { useState } from "react";
import { AgentChatCore } from "@/components/agent-chat-core";

export function GlobalAgentWidget() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  // Die Studio-Seite "Agent" zeigt den Assistenten bereits als volle Ansicht.
  // Dort blenden wir die schwebende Box aus, um Duplikate zu vermeiden.
  if (pathname === "/studio/agent") return null;

  return (
    <aside
      aria-label="Engineering-Assistent"
      className={`agent-widget ${collapsed ? "collapsed" : ""}`}
    >
      {collapsed ? (
        <button
          className="agent-widget-tab"
          onClick={() => setCollapsed(false)}
          type="button"
          aria-label="Agent öffnen"
        >
          <span className="agent-widget-tab-dot" aria-hidden="true" />
          Agent
        </button>
      ) : (
        <div className="agent-widget-panel">
          <div className="agent-widget-header">
            <div>
              <p className="agent-widget-eyebrow">Engineering-Assistent</p>
              <strong>Agent</strong>
            </div>
            <button
              className="agent-widget-collapse"
              onClick={() => setCollapsed(true)}
              type="button"
              aria-label="Agent minimieren"
            >
              ›
            </button>
          </div>

          <div className="agent-widget-body">
            <AgentChatCore compact />
          </div>
        </div>
      )}
    </aside>
  );
}

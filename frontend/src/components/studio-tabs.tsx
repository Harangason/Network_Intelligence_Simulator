"use client";

import Link from "next/link";
import { SimulationWizard } from "./simulation-wizard";
import { EngineeringWorkbench } from "./engineering-workbench";
import { AgentChat } from "./agent-chat";

export type StudioTab = "simulation" | "engineering" | "agent";

export function StudioTabs({
  activeTab,
  initialMode,
}: {
  activeTab: StudioTab;
  initialMode: "parameters" | "network";
}) {
  return (
    <>
      <div className="studio-mode-tabs" role="tablist" aria-label="Studio-Bereich">
        <Link
          aria-selected={activeTab === "simulation"}
          className={activeTab === "simulation" ? "active" : ""}
          href="/studio"
          role="tab"
        >
          Simulation
        </Link>
        <Link
          aria-selected={activeTab === "engineering"}
          className={activeTab === "engineering" ? "active" : ""}
          href="/studio/engineering"
          role="tab"
        >
          Engineering-Modell
        </Link>
        <Link
          aria-selected={activeTab === "agent"}
          className={activeTab === "agent" ? "active" : ""}
          href="/studio/agent"
          role="tab"
        >
          Agent
          <span>KI</span>
        </Link>
      </div>

      {activeTab === "simulation" && <SimulationWizard initialMode={initialMode} />}
      {activeTab === "engineering" && <EngineeringWorkbench />}
      {activeTab === "agent" && <AgentChat />}
    </>
  );
}

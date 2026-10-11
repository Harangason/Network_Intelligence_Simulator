"use client";

import { SimulationWizard } from "./simulation-wizard";
import { EngineeringWorkbench } from "./engineering-workbench";
import { RoutingWorkbench } from "./routing-workbench";

export type StudioTab = "simulation" | "engineering" | "routing";

export function StudioTabs({
  activeTab,
  initialProjectId,
  initialMode,
  routingInitialView,
}: {
  activeTab: StudioTab;
  initialProjectId?: string;
  initialMode: "parameters" | "network";
  routingInitialView?: "Table" | "Graph";
}) {
  return (
    <>
      {activeTab === "simulation" && <SimulationWizard initialMode={initialMode} initialProjectId={initialProjectId} />}
      {activeTab === "engineering" && <EngineeringWorkbench />}
      {activeTab === "routing" && <RoutingWorkbench initialProjectId={initialProjectId} initialView={routingInitialView} />}
    </>
  );
}

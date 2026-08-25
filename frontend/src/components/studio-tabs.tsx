"use client";

import { SimulationWizard } from "./simulation-wizard";
import { EngineeringWorkbench } from "./engineering-workbench";
import { RoutingWorkbench } from "./routing-workbench";

export type StudioTab = "simulation" | "engineering" | "routing";

export function StudioTabs({
  activeTab,
  initialMode,
  routingInitialView,
}: {
  activeTab: StudioTab;
  initialMode: "parameters" | "network";
  routingInitialView?: "Table" | "Graph";
}) {
  return (
    <>
      {activeTab === "simulation" && <SimulationWizard initialMode={initialMode} />}
      {activeTab === "engineering" && <EngineeringWorkbench />}
      {activeTab === "routing" && <RoutingWorkbench initialView={routingInitialView} />}
    </>
  );
}

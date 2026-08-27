import { StudioTabs } from "@/components/studio-tabs";
import { StudioWorkflowHero } from "@/components/studio-workflow-hero";
import { StudioTopbar } from "@/components/studio-topbar";
import { WorkflowHeader } from "@/components/workflow-header";
import { redirect } from "next/navigation";

export default async function StudioPage({
  searchParams,
}: {
  searchParams: Promise<{ mode?: string }>;
}) {
  const { mode } = await searchParams;
  if (!mode) {
    redirect("/studio/engineering");
  }
  const initialMode = mode === "network" ? "network" : "parameters";

  return (
    <main className="shell">
      <StudioTopbar />
      <WorkflowHeader />

      <StudioWorkflowHero
        eyebrow={`Workflow ${initialMode === "network" ? "03" : "04"}`}
        title={initialMode === "network" ? "Technische Kommunikationspfade verbinden." : "Technologien und Timing konfigurieren."}
      >
        {initialMode === "network"
          ? "Ordne logische Routen realen Bussen, Interfaces und Gateways zu."
          : "Pflege technologieabhängige Netzwerk-, Message-, QoS- und Gateway-Parameter."}
      </StudioWorkflowHero>

      <StudioTabs activeTab="simulation" initialMode={initialMode} />
    </main>
  );
}

import { StudioTabs } from "@/components/studio-tabs";
import { StudioWorkflowHero } from "@/components/studio-workflow-hero";
import { StudioTopbar } from "@/components/studio-topbar";
import { WorkflowHeader } from "@/components/workflow-header";
import { projectIdFromSearchParams, projectQuerySuffixFromSearchParams, type ProjectQueryRecord } from "@/lib/user-settings";
import { redirect } from "next/navigation";

type StudioSearchParams = ProjectQueryRecord & {
  mode?: string | string[];
};

export default async function StudioPage({
  searchParams,
}: {
  searchParams: Promise<StudioSearchParams>;
}) {
  const params = await searchParams;
  const mode = Array.isArray(params.mode) ? params.mode[0] : params.mode;
  if (!mode) {
    redirect(`/studio/engineering${projectQuerySuffixFromSearchParams(params)}`);
  }
  const initialMode = mode === "network" ? "network" : "parameters";
  const initialProjectId = projectIdFromSearchParams(params);

  return (
    <main className="shell studio-shell">
      <StudioTopbar initialProjectId={initialProjectId} />
      <WorkflowHeader initialProjectId={initialProjectId} />

      <StudioWorkflowHero
        eyebrow={`Workflow ${initialMode === "network" ? "03" : "04"}`}
        initialProjectId={initialProjectId}
        title={initialMode === "network" ? "Technische Kommunikationspfade verbinden." : "Technologien und Timing konfigurieren."}
      >
        {initialMode === "network"
          ? "Ordne logische Routen realen Bussen, Interfaces und Gateways zu."
          : "Pflege technologieabhängige Netzwerk-, Message-, QoS- und Gateway-Parameter."}
      </StudioWorkflowHero>

      <StudioTabs activeTab="simulation" initialMode={initialMode} initialProjectId={initialProjectId} />
    </main>
  );
}

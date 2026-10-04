import { StudioTabs } from "@/features/workflow/ui/studio-tabs";
import { StudioWorkflowHero } from "@/features/workflow/ui/studio-workflow-hero";
import { StudioTopbar } from "@/features/workflow/ui/studio-topbar";
import { WorkflowHeader } from "@/features/workflow/ui/workflow-header";
import { projectIdFromSearchParams, type ProjectQueryRecord } from "@/features/settings/lib/user-settings";

export default async function RoutingPage({
  searchParams,
}: {
  searchParams: Promise<ProjectQueryRecord & { view?: string | string[] }>;
}) {
  const params = await searchParams;
  const view = Array.isArray(params.view) ? params.view[0] : params.view;
  const initialProjectId = projectIdFromSearchParams(params);
  return (
    <main className="shell studio-shell routing-shell">
      <StudioTopbar initialProjectId={initialProjectId} />
      <WorkflowHeader initialProjectId={initialProjectId} />
      <StudioWorkflowHero eyebrow="Routing Manager" initialProjectId={initialProjectId} title="Informationen sicher zu ihren Consumern führen.">
        Technologieunabhängige Kommunikationspfade konfigurieren, prüfen,
        freigeben und direkt für Simulationen verwenden.
      </StudioWorkflowHero>
      <StudioTabs
        activeTab="routing"
        initialProjectId={initialProjectId}
        initialMode="parameters"
        routingInitialView={view === "graph" ? "Graph" : "Table"}
      />
    </main>
  );
}

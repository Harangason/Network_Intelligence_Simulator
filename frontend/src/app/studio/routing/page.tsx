import { StudioTabs } from "@/components/studio-tabs";
import { StudioWorkflowHero } from "@/components/studio-workflow-hero";
import { StudioTopbar } from "@/components/studio-topbar";
import { WorkflowHeader } from "@/components/workflow-header";

export default async function RoutingPage({
  searchParams,
}: {
  searchParams: Promise<{ view?: string }>;
}) {
  const { view } = await searchParams;
  return (
    <main className="shell studio-shell routing-shell">
      <StudioTopbar />
      <WorkflowHeader />
      <StudioWorkflowHero eyebrow="Routing Manager" title="Informationen sicher zu ihren Consumern führen.">
        Technologieunabhängige Kommunikationspfade konfigurieren, prüfen,
        freigeben und direkt für Simulationen verwenden.
      </StudioWorkflowHero>
      <StudioTabs
        activeTab="routing"
        initialMode="parameters"
        routingInitialView={view === "graph" ? "Graph" : "Table"}
      />
    </main>
  );
}

import { StudioTabs } from "@/components/studio-tabs";
import { StudioTopbar } from "@/components/studio-topbar";
import { WorkflowHeader } from "@/components/workflow-header";

export default async function RoutingPage({
  searchParams,
}: {
  searchParams: Promise<{ view?: string }>;
}) {
  const { view } = await searchParams;
  return (
    <main className="shell routing-shell">
      <StudioTopbar />
      <WorkflowHeader />
      <section className="hero routing-hero">
        <div>
          <p className="eyebrow">Routing Manager</p>
          <h1>Informationen sicher zu ihren Consumern führen.</h1>
          <p className="hero-copy">
            Technologieunabhängige Kommunikationspfade konfigurieren, prüfen,
            freigeben und direkt für Simulationen verwenden.
          </p>
        </div>
        <div className="hero-stat">
          <span>Governance</span>
          <strong>HITL</strong>
          <small>Validate · Review · Approve</small>
        </div>
      </section>
      <StudioTabs
        activeTab="routing"
        initialMode="parameters"
        routingInitialView={view === "graph" ? "Graph" : "Table"}
      />
    </main>
  );
}

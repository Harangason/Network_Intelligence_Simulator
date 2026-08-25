import { IntelligenceWorkbench } from "@/components/intelligence-workbench";
import { StudioTopbar } from "@/components/studio-topbar";
import { WorkflowHeader } from "@/components/workflow-header";

export default function IntelligencePage() {
  return (
    <main className="shell workflow-shell">
      <StudioTopbar />
      <WorkflowHeader />
      <section className="workflow-page-heading">
        <div>
          <p className="eyebrow">Workflow 09</p>
          <h1>Systemqualität bewerten. Schwächen gezielt verbessern.</h1>
          <p>Deterministische Analytics verbinden Engineering-Modell, Graph, Routing, Capacity, Validation und Simulation. Vorschläge bleiben bis zum Human Review getrennt.</p>
        </div>
        <div className="hero-stat"><span>Intelligence</span><strong>DS</strong><small>assess · learn · improve</small></div>
      </section>
      <IntelligenceWorkbench />
    </main>
  );
}

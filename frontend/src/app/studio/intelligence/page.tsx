import { IntelligenceWorkbench } from "@/components/intelligence-workbench";
import { StudioWorkflowHero } from "@/components/studio-workflow-hero";
import { StudioTopbar } from "@/components/studio-topbar";
import { WorkflowHeader } from "@/components/workflow-header";

export default function IntelligencePage() {
  return (
    <main className="shell studio-shell workflow-shell">
      <StudioTopbar />
      <WorkflowHeader />
      <StudioWorkflowHero eyebrow="Workflow 09" title="Systemqualität bewerten. Schwächen gezielt verbessern.">
        Deterministische Analytics verbinden Engineering-Modell, Graph, Routing, Capacity, Validation und Simulation. Vorschläge bleiben bis zum Human Review getrennt.
      </StudioWorkflowHero>
      <IntelligenceWorkbench />
    </main>
  );
}

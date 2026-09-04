import { IntelligenceWorkbench } from "@/components/intelligence-workbench";
import { StudioWorkflowHero } from "@/components/studio-workflow-hero";
import { StudioTopbar } from "@/components/studio-topbar";
import { WorkflowHeader } from "@/components/workflow-header";
import { projectIdFromSearchParams, type ProjectQueryRecord } from "@/lib/user-settings";

export default async function IntelligencePage({
  searchParams,
}: {
  searchParams: Promise<ProjectQueryRecord>;
}) {
  const initialProjectId = projectIdFromSearchParams(await searchParams);
  return (
    <main className="shell studio-shell workflow-shell">
      <StudioTopbar initialProjectId={initialProjectId} />
      <WorkflowHeader initialProjectId={initialProjectId} />
      <StudioWorkflowHero eyebrow="Workflow 09" initialProjectId={initialProjectId} title="Systemqualität bewerten. Schwächen gezielt verbessern.">
        Deterministische Analytics verbinden Engineering-Modell, Graph, Routing, Capacity, Validation und Simulation. Vorschläge bleiben bis zum Human Review getrennt.
      </StudioWorkflowHero>
      <IntelligenceWorkbench />
    </main>
  );
}

import { IntelligenceWorkbench } from "@/features/workflow/stage_09_intelligence/index.ts";
import { StudioWorkflowHero } from "@/features/workflow/ui/studio-workflow-hero";
import { StudioTopbar } from "@/features/workflow/ui/studio-topbar";
import { WorkflowHeader } from "@/features/workflow/ui/workflow-header";
import { projectIdFromSearchParams, type ProjectQueryRecord } from "@/features/settings/lib/user-settings";

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

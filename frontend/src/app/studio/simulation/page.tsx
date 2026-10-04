import { ModelSimulationRunner } from "@/features/workflow/stage_07_simulation/index.ts";
import { StudioWorkflowHero } from "@/features/workflow/ui/studio-workflow-hero";
import { StudioTopbar } from "@/features/workflow/ui/studio-topbar";
import { WorkflowHeader } from "@/features/workflow/ui/workflow-header";
import { projectIdFromSearchParams, type ProjectQueryRecord } from "@/features/settings/lib/user-settings";

export default async function WorkflowSimulationPage({
  searchParams,
}: {
  searchParams: Promise<ProjectQueryRecord>;
}) {
  const initialProjectId = projectIdFromSearchParams(await searchParams);
  return (
    <main className="shell studio-shell workflow-shell">
      <StudioTopbar initialProjectId={initialProjectId} />
      <WorkflowHeader initialProjectId={initialProjectId} />
      <StudioWorkflowHero eyebrow="Workflow 07" initialProjectId={initialProjectId} title="Signale und Kommunikation gemeinsam simulieren.">
        Modellwerte, Frames, Buslast und Fehlerereignisse laufen auf einer synchronisierten Zeitachse.
      </StudioWorkflowHero>
      <ModelSimulationRunner initialProjectId={initialProjectId} />
    </main>
  );
}

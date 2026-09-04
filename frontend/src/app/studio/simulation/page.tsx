import { ModelSimulationRunner } from "@/components/model-simulation-runner";
import { StudioWorkflowHero } from "@/components/studio-workflow-hero";
import { StudioTopbar } from "@/components/studio-topbar";
import { WorkflowHeader } from "@/components/workflow-header";
import { projectIdFromSearchParams, type ProjectQueryRecord } from "@/lib/user-settings";

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

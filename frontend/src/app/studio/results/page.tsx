import { ResultsWorkbench } from "@/components/results-workbench";
import { StudioWorkflowHero } from "@/components/studio-workflow-hero";
import { StudioTopbar } from "@/components/studio-topbar";
import { WorkflowHeader } from "@/components/workflow-header";
import { projectIdFromSearchParams, type ProjectQueryRecord } from "@/lib/user-settings";

export default async function ResultsPage({
  searchParams,
}: {
  searchParams: Promise<ProjectQueryRecord>;
}) {
  const initialProjectId = projectIdFromSearchParams(await searchParams);
  return (
    <main className="shell studio-shell workflow-shell">
      <StudioTopbar initialProjectId={initialProjectId} />
      <WorkflowHeader initialProjectId={initialProjectId} />
      <StudioWorkflowHero eyebrow="Workflow 08" initialProjectId={initialProjectId} title="Prognose und Simulation gemeinsam analysieren.">
        Historische Ergebnisse bleiben erhalten, einschließlich Quellversionen, Veraltungsgrund und technischer Evidenz.
      </StudioWorkflowHero>
      <ResultsWorkbench initialProjectId={initialProjectId} />
    </main>
  );
}

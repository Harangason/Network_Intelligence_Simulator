import { ResultsWorkbench } from "@/features/workflow/stage_08_results_analysis/index.ts";
import { StudioWorkflowHero } from "@/features/workflow/ui/studio-workflow-hero";
import { StudioTopbar } from "@/features/workflow/ui/studio-topbar";
import { WorkflowHeader } from "@/features/workflow/ui/workflow-header";
import { projectIdFromSearchParams, type ProjectQueryRecord } from "@/features/settings/lib/user-settings";

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

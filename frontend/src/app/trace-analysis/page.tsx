import { StudioWorkflowHero } from "@/features/workflow/ui/studio-workflow-hero";
import { StudioTopbar } from "@/features/workflow/ui/studio-topbar";
import { TraceAnalysisWorkbench } from "@/features/traces/ui/trace-analysis-workbench";
import { WorkflowHeader } from "@/features/workflow/ui/workflow-header";
import { projectIdFromSearchParams, type ProjectQueryRecord } from "@/features/settings/lib/user-settings";

export default async function TraceAnalysisPage({
  searchParams,
}: {
  searchParams: Promise<ProjectQueryRecord>;
}) {
  const query=await searchParams;
  const initialProjectId = projectIdFromSearchParams(query);
  const secondary=Boolean(query.window && query.primary && query.window!==query.primary);
  return (
    <main className="shell studio-shell workflow-shell trace-analysis-page">
      {secondary ? <header className="analysis-secondary-heading"><strong>NIS · Analysefenster</strong><span>Gespeicherte Daten · Analyseprojektion</span></header> : <StudioTopbar initialProjectId={initialProjectId} />}
      <WorkflowHeader initialProjectId={initialProjectId} variant="trace-analysis" />
      <StudioWorkflowHero eyebrow="Trace Analyse" initialProjectId={initialProjectId} title="Trace-Artefakte analysieren.">
        Botschaften, Sequenzen, Signale und Findings werden aus geladenen Trace-Artefakten untersucht. Engineering-Daten werden nicht verändert.
      </StudioWorkflowHero>
      <TraceAnalysisWorkbench />
    </main>
  );
}

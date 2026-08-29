import { StudioWorkflowHero } from "@/components/studio-workflow-hero";
import { StudioTopbar } from "@/components/studio-topbar";
import { TraceAnalysisWorkbench } from "@/components/trace-analysis-workbench";
import { WorkflowHeader } from "@/components/workflow-header";

export default function TraceAnalysisPage() {
  return (
    <main className="shell studio-shell workflow-shell trace-analysis-page">
      <StudioTopbar />
      <WorkflowHeader variant="trace-analysis" />
      <StudioWorkflowHero eyebrow="Trace Analyse" title="Trace-Artefakte analysieren.">
        Botschaften, Sequenzen, Signale und Findings werden aus geladenen Trace-Artefakten untersucht. Engineering-Daten werden nicht verändert.
      </StudioWorkflowHero>
      <TraceAnalysisWorkbench />
    </main>
  );
}

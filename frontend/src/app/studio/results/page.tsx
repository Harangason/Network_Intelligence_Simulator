import { ResultsWorkbench } from "@/components/results-workbench";
import { StudioWorkflowHero } from "@/components/studio-workflow-hero";
import { StudioTopbar } from "@/components/studio-topbar";
import { WorkflowHeader } from "@/components/workflow-header";

export default function ResultsPage() {
  return <main className="shell studio-shell workflow-shell"><StudioTopbar /><WorkflowHeader /><StudioWorkflowHero eyebrow="Workflow 08" title="Prognose und Simulation gemeinsam analysieren.">Historische Ergebnisse bleiben erhalten, einschließlich Quellversionen, Veraltungsgrund und technischer Evidenz.</StudioWorkflowHero><ResultsWorkbench /></main>;
}

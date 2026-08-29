import { ModelSimulationRunner } from "@/components/model-simulation-runner";
import { StudioWorkflowHero } from "@/components/studio-workflow-hero";
import { StudioTopbar } from "@/components/studio-topbar";
import { WorkflowHeader } from "@/components/workflow-header";

export default function WorkflowSimulationPage() {
  return <main className="shell studio-shell workflow-shell"><StudioTopbar /><WorkflowHeader /><StudioWorkflowHero eyebrow="Workflow 07" title="Signale und Kommunikation gemeinsam simulieren.">Modellwerte, Frames, Buslast und Fehlerereignisse laufen auf einer synchronisierten Zeitachse.</StudioWorkflowHero><ModelSimulationRunner /></main>;
}

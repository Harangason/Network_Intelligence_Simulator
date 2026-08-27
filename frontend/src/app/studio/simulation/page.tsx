import { SimulationRunner } from "@/components/simulation-runner";
import { StudioWorkflowHero } from "@/components/studio-workflow-hero";
import { StudioTopbar } from "@/components/studio-topbar";
import { WorkflowHeader } from "@/components/workflow-header";

export default function WorkflowSimulationPage() {
  return <main className="shell workflow-shell"><StudioTopbar /><WorkflowHeader /><StudioWorkflowHero eyebrow="Workflow 07" title="Einen validierten Snapshot simulieren.">Start, Laufstatus und Failure Injection liegen hier. Engineering-Daten werden während des Laufs nicht verändert.</StudioWorkflowHero><SimulationRunner /></main>;
}

import { SimulationRunner } from "@/components/simulation-runner";
import { StudioTopbar } from "@/components/studio-topbar";
import { WorkflowHeader } from "@/components/workflow-header";

export default function WorkflowSimulationPage() {
  return <main className="shell workflow-shell"><StudioTopbar /><WorkflowHeader /><section className="workflow-page-heading"><div><p className="eyebrow">Workflow 07</p><h1>Einen validierten Snapshot simulieren.</h1><p>Start, Laufstatus und Failure Injection liegen hier. Engineering-Daten werden während des Laufs nicht verändert.</p></div><div className="hero-stat"><span>Input</span><strong>LOCK</strong><small>immutable snapshot</small></div></section><SimulationRunner /></main>;
}

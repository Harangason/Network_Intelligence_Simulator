import { CapacityWorkbench } from "@/components/capacity-workbench";
import { StudioTopbar } from "@/components/studio-topbar";
import { WorkflowHeader } from "@/components/workflow-header";

export default function CapacityPage() {
  return <main className="shell workflow-shell"><StudioTopbar /><WorkflowHeader /><section className="workflow-page-heading"><div><p className="eyebrow">Workflow 05</p><h1>Kapazität und Timing vor dem Lauf verstehen.</h1><p>Buslast, Peak/Burst Load, Reserve, Queueing, Gateway-Last und End-to-End-Latenz werden versioniert berechnet.</p></div><div className="hero-stat"><span>Berechnung</span><strong>PRE</strong><small>vor Validation</small></div></section><CapacityWorkbench /></main>;
}

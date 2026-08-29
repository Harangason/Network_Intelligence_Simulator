import { CapacityWorkbench } from "@/components/capacity-workbench";
import { StudioWorkflowHero } from "@/components/studio-workflow-hero";
import { StudioTopbar } from "@/components/studio-topbar";
import { WorkflowHeader } from "@/components/workflow-header";

export default function CapacityPage() {
  return <main className="shell studio-shell workflow-shell"><StudioTopbar /><WorkflowHeader /><StudioWorkflowHero eyebrow="Workflow 05" title="Kapazität und Timing vor dem Lauf verstehen.">Buslast, Peak/Burst Load, Reserve, Queueing, Gateway-Last und End-to-End-Latenz werden versioniert berechnet.</StudioWorkflowHero><CapacityWorkbench /></main>;
}

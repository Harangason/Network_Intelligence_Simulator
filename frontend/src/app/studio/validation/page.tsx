import { PreflightWorkbench } from "@/components/preflight-workbench";
import { StudioWorkflowHero } from "@/components/studio-workflow-hero";
import { StudioTopbar } from "@/components/studio-topbar";
import { WorkflowHeader } from "@/components/workflow-header";

export default function ValidationPage() {
  return <main className="shell studio-shell workflow-shell"><StudioTopbar /><WorkflowHeader /><StudioWorkflowHero eyebrow="Workflow 06" title="Technische Konsistenz vor der Simulation prüfen.">ERROR blockiert. WARNING bleibt sichtbar und ist zulässig. Der Preflight bindet alle Quellversionen.</StudioWorkflowHero><PreflightWorkbench /></main>;
}

import { PreflightWorkbench } from "@/components/preflight-workbench";
import { StudioTopbar } from "@/components/studio-topbar";
import { WorkflowHeader } from "@/components/workflow-header";

export default function ValidationPage() {
  return <main className="shell workflow-shell"><StudioTopbar /><WorkflowHeader /><section className="workflow-page-heading"><div><p className="eyebrow">Workflow 06</p><h1>Technische Konsistenz vor der Simulation prüfen.</h1><p>ERROR blockiert. WARNING bleibt sichtbar und ist zulässig. Der Preflight bindet alle Quellversionen.</p></div><div className="hero-stat"><span>Gate</span><strong>V&V</strong><small>versioniert</small></div></section><PreflightWorkbench /></main>;
}

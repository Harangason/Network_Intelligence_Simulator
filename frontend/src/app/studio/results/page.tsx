import { ResultsWorkbench } from "@/components/results-workbench";
import { StudioTopbar } from "@/components/studio-topbar";
import { WorkflowHeader } from "@/components/workflow-header";

export default function ResultsPage() {
  return <main className="shell workflow-shell"><StudioTopbar /><WorkflowHeader /><section className="workflow-page-heading"><div><p className="eyebrow">Workflow 08</p><h1>Prognose und Simulation gemeinsam analysieren.</h1><p>Historische Ergebnisse bleiben erhalten, einschließlich Quellversionen, Veraltungsgrund und technischer Evidenz.</p></div><div className="hero-stat"><span>Analyse</span><strong>Δ</strong><small>calculated vs observed</small></div></section><ResultsWorkbench /></main>;
}

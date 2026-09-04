import { PreflightWorkbench } from "@/components/preflight-workbench";
import { StudioWorkflowHero } from "@/components/studio-workflow-hero";
import { StudioTopbar } from "@/components/studio-topbar";
import { WorkflowHeader } from "@/components/workflow-header";
import { projectIdFromSearchParams, type ProjectQueryRecord } from "@/lib/user-settings";

export default async function ValidationPage({
  searchParams,
}: {
  searchParams: Promise<ProjectQueryRecord>;
}) {
  const initialProjectId = projectIdFromSearchParams(await searchParams);
  return (
    <main className="shell studio-shell workflow-shell">
      <StudioTopbar initialProjectId={initialProjectId} />
      <WorkflowHeader initialProjectId={initialProjectId} />
      <StudioWorkflowHero eyebrow="Workflow 06" initialProjectId={initialProjectId} title="Technische Konsistenz vor der Simulation prüfen.">
        ERROR blockiert. WARNING bleibt sichtbar und ist zulässig. Der Preflight bindet alle Quellversionen.
      </StudioWorkflowHero>
      <PreflightWorkbench initialProjectId={initialProjectId} />
    </main>
  );
}
